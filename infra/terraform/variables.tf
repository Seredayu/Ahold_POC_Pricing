variable "azure_subscription_id" {
  description = "Azure subscription ID"
  type        = string
}

variable "project_name" {
  description = "Project slug used in resource names"
  type        = string
  default     = "ahold-poc"
}

variable "environment" {
  description = "Deployment environment (poc, staging, prod)"
  type        = string
  default     = "poc"
}

variable "location" {
  description = "Azure region (Belgium Delhaize: West Europe)"
  type        = string
  default     = "westeurope"
}

variable "bff_image" {
  description = "Container image for Node.js BFF (e.g. ghcr.io/org/bff:latest)"
  type        = string
}

variable "btp_destination_name" {
  description = "SAP BTP Destination Service name for ECC RFC connection"
  type        = string
  default     = "ECC-RFC-BE"
}

variable "btp_oauth_token_url" {
  description = "BTP xsuaa OAuth token URL"
  type        = string
}

variable "btp_destination_svc_url" {
  description = "BTP Destination Service API base URL"
  type        = string
}

variable "btp_client_id" {
  description = "BTP OAuth client ID (sensitive)"
  type        = string
  sensitive   = true
}

variable "btp_client_secret" {
  description = "BTP OAuth client secret (sensitive)"
  type        = string
  sensitive   = true
}

variable "sap_host" {
  description = "SAP ECC 6.0 application server hostname (via BTP Cloud Connector)"
  type        = string
}

variable "sap_client" {
  description = "SAP client number (e.g. 100)"
  type        = string
  default     = "100"
}

variable "sap_sysnr" {
  description = "SAP system number (e.g. 00)"
  type        = string
  default     = "00"
}
