terraform {
  required_version = ">= 1.7.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    databricks = {
      source  = "databricks/databricks"
      version = "~> 1.40"
    }
  }

  backend "azurerm" {
    resource_group_name  = "rg-ahold-poc-tfstate"
    storage_account_name = "saaholdpoctfstate"
    container_name       = "tfstate"
    key                  = "ahold-poc-pricing.tfstate"
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
}

provider "databricks" {
  azure_workspace_resource_id = azurerm_databricks_workspace.this.id
}

# ---------------------------------------------------------------------------
# Resource group
# ---------------------------------------------------------------------------

resource "azurerm_resource_group" "this" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location
  tags     = local.tags
}

# ---------------------------------------------------------------------------
# Databricks workspace (Premium — required for Unity Catalog + Model Serving)
# ---------------------------------------------------------------------------

resource "azurerm_databricks_workspace" "this" {
  name                = "dbw-${var.project_name}-${var.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = azurerm_resource_group.this.location
  sku                 = "premium"

  custom_parameters {
    storage_account_name          = "dbwstore${replace(var.project_name, "-", "")}"
    storage_account_sku_name      = "Standard_LRS"
    virtual_network_id            = azurerm_virtual_network.this.id
    private_subnet_name           = azurerm_subnet.dbw_private.name
    public_subnet_name            = azurerm_subnet.dbw_public.name
    public_subnet_network_security_group_association_id  = azurerm_subnet_network_security_group_association.dbw_public.id
    private_subnet_network_security_group_association_id = azurerm_subnet_network_security_group_association.dbw_private.id
  }

  tags = local.tags
}

# ---------------------------------------------------------------------------
# Networking (VNet injection for BTP Cloud Connector access)
# ---------------------------------------------------------------------------

resource "azurerm_virtual_network" "this" {
  name                = "vnet-${var.project_name}-${var.environment}"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_subnet" "dbw_public" {
  name                 = "snet-dbw-public"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.0.1.0/24"]

  delegation {
    name = "databricks-del"
    service_delegation {
      name = "Microsoft.Databricks/workspaces"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
        "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
        "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action",
      ]
    }
  }
}

resource "azurerm_subnet" "dbw_private" {
  name                 = "snet-dbw-private"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.0.2.0/24"]

  delegation {
    name = "databricks-del"
    service_delegation {
      name = "Microsoft.Databricks/workspaces"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
        "Microsoft.Network/virtualNetworks/subnets/prepareNetworkPolicies/action",
        "Microsoft.Network/virtualNetworks/subnets/unprepareNetworkPolicies/action",
      ]
    }
  }
}

resource "azurerm_subnet" "aca" {
  name                 = "snet-aca"
  resource_group_name  = azurerm_resource_group.this.name
  virtual_network_name = azurerm_virtual_network.this.name
  address_prefixes     = ["10.0.3.0/24"]

  delegation {
    name = "aca-del"
    service_delegation {
      name = "Microsoft.App/environments"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_network_security_group" "dbw" {
  name                = "nsg-dbw-${var.environment}"
  location            = azurerm_resource_group.this.location
  resource_group_name = azurerm_resource_group.this.name
  tags                = local.tags
}

resource "azurerm_subnet_network_security_group_association" "dbw_public" {
  subnet_id                 = azurerm_subnet.dbw_public.id
  network_security_group_id = azurerm_network_security_group.dbw.id
}

resource "azurerm_subnet_network_security_group_association" "dbw_private" {
  subnet_id                 = azurerm_subnet.dbw_private.id
  network_security_group_id = azurerm_network_security_group.dbw.id
}

# ---------------------------------------------------------------------------
# ADLS Gen2 storage (Databricks Unity Catalog metastore root)
# ---------------------------------------------------------------------------

resource "azurerm_storage_account" "datalake" {
  name                     = "adls${replace(var.project_name, "-", "")}${var.environment}"
  resource_group_name      = azurerm_resource_group.this.name
  location                 = azurerm_resource_group.this.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"
  is_hns_enabled           = true   # hierarchical namespace = ADLS Gen2
  tags                     = local.tags
}

resource "azurerm_storage_container" "unity_catalog" {
  name                  = "unity-catalog"
  storage_account_name  = azurerm_storage_account.datalake.name
  container_access_type = "private"
}

# ---------------------------------------------------------------------------
# Azure Container Apps — Node.js BFF (Phase 2B)
# ---------------------------------------------------------------------------

data "azurerm_container_app_environment" "this" {
  name                = "ahpoc-cae"
  resource_group_name = "rg-ahold-freshness-poc"
}

resource "azurerm_container_app" "bff" {
  name                         = "ca-bff-${var.environment}"
  container_app_environment_id = data.azurerm_container_app_environment.this.id
  resource_group_name          = azurerm_resource_group.this.name
  revision_mode                = "Single"
  tags                         = local.tags

  template {
    container {
      name   = "bff"
      image  = var.bff_image
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name  = "BTP_ENABLED"
        value = "true"
      }
      env {
        name        = "BTP_CLIENT_ID"
        secret_name = "btp-client-id"
      }
      env {
        name        = "BTP_CLIENT_SECRET"
        secret_name = "btp-client-secret"
      }
      env {
        name  = "BTP_DESTINATION_NAME"
        value = var.btp_destination_name
      }
      env {
        name  = "BTP_OAUTH_TOKEN_URL"
        value = var.btp_oauth_token_url
      }
      env {
        name  = "BTP_DESTINATION_SVC_URL"
        value = var.btp_destination_svc_url
      }
    }

    min_replicas = 1
    max_replicas = 3
  }

  ingress {
    external_enabled = true
    target_port      = 3001
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  secret {
    name  = "btp-client-id"
    value = var.btp_client_id
  }
  secret {
    name  = "btp-client-secret"
    value = var.btp_client_secret
  }
}

# ---------------------------------------------------------------------------
# Databricks resources (Unity Catalog + DLT pipeline)
# Requires Unity Catalog metastore setup in Databricks Account Console first.
# Steps: https://docs.databricks.com/en/data-governance/unity-catalog/get-started.html
# Re-enable after metastore is configured and linked to this workspace.
# ---------------------------------------------------------------------------

# resource "databricks_catalog" "ahold_poc" { ... }
# resource "databricks_schema" "bronze/silver/gold" { ... }
# resource "databricks_pipeline" "freshness" { ... }
# Uncomment after running: infra/databricks/setup-unity-catalog.md

# ---------------------------------------------------------------------------
# Locals
# ---------------------------------------------------------------------------

locals {
  tags = {
    project     = var.project_name
    environment = var.environment
    managed_by  = "terraform"
  }
}
