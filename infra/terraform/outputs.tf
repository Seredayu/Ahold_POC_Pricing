output "databricks_workspace_url" {
  description = "Databricks workspace URL"
  value       = "https://${azurerm_databricks_workspace.this.workspace_url}"
}

output "bff_url" {
  description = "Azure Container Apps BFF ingress URL"
  value       = "https://${azurerm_container_app.bff.latest_revision_fqdn}"
}

output "datalake_storage_account" {
  description = "ADLS Gen2 storage account name"
  value       = azurerm_storage_account.datalake.name
}

output "dlt_pipeline_id" {
  description = "Databricks DLT pipeline ID (use in job trigger)"
  value       = databricks_pipeline.freshness.id
}
