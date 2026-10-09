####################################################################################
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#     https://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
####################################################################################

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google-beta"
      version = "5.35.0"
    }
  }
}


####################################################################################
# Variables
####################################################################################
variable "project_id" {}
variable "multi_region" {}
variable "vertex_ai_region" {}
variable "bigquery_DEMO-NAME-UNDERSCORE_dataset" {}
variable "DEMO-NAME-UNDERSCORE_bucket" {}
variable "DEMO-NAME-UNDERSCORE_code_bucket" {}
variable "dataform_region" {}
variable "random_extension" {}
variable "gcp_account_name" {}
variable "dataflow_staging_bucket" {}
variable "dataflow_service_account" {}


data "google_client_config" "current" {
}


# Define the list of notebook files to be created
locals {
  DEMO-NAME-UNDERSCORE_notebooks = [
    for s in fileset("../colab-enterprise/", "*.ipynb") : trimsuffix(s, ".ipynb")
  ]

  notebook_names = local.DEMO-NAME-UNDERSCORE_notebooks # concat(local.TTTT, local.DEMO-NAME-UNDERSCORE_notebooks)
}


resource "null_resource" "commit_DEMO-NAME-UNDERSCORE_notebooks" {
  count = length(local.DEMO-NAME-UNDERSCORE_notebooks)

  triggers = {
    always_run = timestamp()
  }

  provisioner "local-exec" {

    when    = create
    command = <<EOF
curl -X POST \
  https://dataform.googleapis.com/v1beta1/projects/${var.project_id}/locations/${var.dataform_region}/repositories/${replace(local.DEMO-NAME-UNDERSCORE_notebooks[count.index], ".ipynb", "")}:commit \
  --header "Authorization: Bearer ${data.google_client_config.current.access_token}" \
  --header "Content-Type: application/json" \
  --compressed \
  --data "@../terraform-modules/colab-deployment-create-files/notebooks_base64/${local.DEMO-NAME-UNDERSCORE_notebooks[count.index]}.base64"
EOF
  }
  depends_on = []
}