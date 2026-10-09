/*##################################################################################
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
###################################################################################*/

/*
Author: Adam Paternostro 

Use Cases:
    - Initializes the system (you can re-run this)

Description: 
    - Loads all tables from the public storage account
    - Uses AVRO so we can bring in JSON and GEO types

References:
    - 

Clean up / Reset script:
    -  n/a

*/


------------------------------------------------------------------------------------------------------------
-- Create GenAI / Vertex AI connections
------------------------------------------------------------------------------------------------------------
CREATE MODEL IF NOT EXISTS `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.gemini_pro`
  REMOTE WITH CONNECTION `${project_id}.us.vertex-ai`
  OPTIONS (endpoint = 'gemini-pro');

CREATE MODEL IF NOT EXISTS `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.gemini_pro_1_5`
  REMOTE WITH CONNECTION `${project_id}.us.vertex-ai`
  OPTIONS (endpoint = 'gemini-1.5-pro-001');

CREATE MODEL IF NOT EXISTS `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.google-textembedding`
  REMOTE WITH CONNECTION `${project_id}.us.vertex-ai`
  OPTIONS (endpoint = 'text-embedding-004');


------------------------------------------------------------------------------------------------------------
-- Load all data
------------------------------------------------------------------------------------------------------------
LOAD DATA OVERWRITE `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.campaign` 
CLUSTER BY campaign_id 
FROM FILES ( format = 'AVRO', enable_logical_types = true, uris = ['gs://data-analytics-golden-demo/DEMO-NAME/v1/Data-Export/campaign/campaign_*.avro']);


------------------------------------------------------------------------------------------------------------
-- Create Views
------------------------------------------------------------------------------------------------------------
/*
CREATE OR REPLACE VIEW `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.insights`(
          store_name OPTIONS (DESCRIPTION='Name of the Store'),
          store_address OPTIONS (DESCRIPTION='The address of the store'),
          store_latitude OPTIONS (DESCRIPTION='Latitude of the store'),
          store_longitude OPTIONS (DESCRIPTION='Longitude of the store'),
          customer_name OPTIONS (DESCRIPTION='Name of the customer'),
          customer_email OPTIONS (DESCRIPTION='Email address of the customer'),
          customer_inception_date OPTIONS (DESCRIPTION='Date when the customer first joined'),
          customer_yob OPTIONS (DESCRIPTION='Year of birth of the customer'),
          order_datetime OPTIONS (DESCRIPTION='Timestamp when the order was placed'),
          order_completion_datetime OPTIONS (DESCRIPTION='Timestamp when the order was completed'),
          menu_name OPTIONS (DESCRIPTION='Name of the item on the menu'),
          menu_price OPTIONS (DESCRIPTION='Price of the menu item'),
          menu_size OPTIONS (DESCRIPTION='Size of the menu item (e.g., small, medium, large)'),
          menu_description OPTIONS (DESCRIPTION='Description of the menu item'),
          menu_alergy_info OPTIONS (DESCRIPTION='Allergy information for the menu item'),
          quantity OPTIONS (DESCRIPTION='Quantity of the menu item ordered'),
          item_total OPTIONS (DESCRIPTION='Total price of the item (quantity * menu_price)'),
          item_price OPTIONS (DESCRIPTION='Price of the individual item'), 
          item_size OPTIONS (DESCRIPTION='Size of the individual item')) AS 
   SELECT store_name,
          store_address,
          store_latitude,
          store_longitude,
          customer_name,
          customer_email,
          customer_inception_date,
          customer_yob,
          order_datetime,
          order_completion_datetime,
          menu_name,
          menu_price,
          menu_size,
          menu_description,
          menu_alergy_info,
          quantity,
          item_total,
          item_price,
          item_size
  FROM `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.store` store
       INNER JOIN `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.order` orders
               ON store.store_id = orders.store_id
       INNER JOIN `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.order_item` order_item
               ON order_item.order_id=orders.order_id
       INNER JOIN `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.menu` menu
               ON menu.menu_id=order_item.menu_id
       INNER JOIN `${project_id}.${bigquery_DEMO-NAME-UNDERSCORE_dataset}.customer` customer
               ON customer.customer_id=orders.customer_id;
*/

-- You cannot end Terraform on a comment, so this just prevents the error.
SELECT 1;