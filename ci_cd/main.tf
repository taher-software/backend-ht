terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "7.26.0"
      
    }
  }
   cloud {
        organization = "bodor"

        workspaces {
            name = "backend-ht"
        }
  }
}

provider "google" {
  project = var.project_id
  credentials = var.gcp_credentials
}

locals {
    schedulers = {
        Breakfast-meal-reminder = {
            schedule = "0 * * * *"
            description = "Send breakfast meal reminder: 2 hours before breajfast menu time"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/meals/send-breakfast-reminder"
        }

        Breakfast-menu-notification = {
            schedule = "0 * * * *"
            description = "Send breakfast menu notification: at breakfast menu time"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/menu/trigger_breakfast_notifications"
        }

        daily-restaurant-survey = {
            schedule = "0 * * * *"
            description = "Send daily restaurant survey"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/surveys/trigger-restaurant-survey"
        }

        daily-room-survey = {
            schedule = "0 * * * *"
            description = "Send daily room survey"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/surveys/trigger-daily-survey"
        }

        dinner-meal-reminder = {
            schedule = "0 * * * *"
            description = "Send dinner meal reminder: 2 hours before dinner menu time"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/meals/send-dinner-reminder"
        }

        Dinner-menu-notification = {
            schedule = "0 * * * *"
            description = "Send dinner menu notification: at dinner menu time"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/menu/trigger_dinner_notifications"
        }

        lunch-meal-reminder = {
            schedule = "0 * * * *"
            description = "Send lunch meal reminder: 2 hours before lunch menu time"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/meals/send-lunch-reminder"
        }

        Lunch-menu-notification = {
            schedule = "0 * * * *"
            description = "Send lunch menu notification: at lunch menu time"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/menu/trigger_lunch_notifications"
        }

        Assignments-plan-notification = {
            schedule = "0 */6 * * *"
            description = "Send assignments plan reminder"
            uri = "https://bodor-web-app-368726253523.europe-west1.run.app/assignments/plan_assignments_reminder"
        }

    }

    services = {
        bodor-chat = {
            allow_public = true
            min_instances = 1
            max_instances = 1
            cloud_sql_connection = google_sql_database_instance.bodor.connection_name
        }

        bodor-web-app = {
            allow_public = true
            min_instances = 0
            max_instances = 100
            cloud_sql_connection = google_sql_database_instance.bodor.connection_name
        }

        worker-bodor = {
            allow_public = false
            min_instances = 0
            max_instances = 20
            cloud_sql_connection = google_sql_database_instance.bodor.connection_name
        }
    }
}

module "scheduler" {
  source = "./modules/cloud_scheduler"

  for_each = local.schedulers

  name     = each.key
  schedule = each.value.schedule
  uri      = each.value.uri
  description = each.value.description
}

resource "google_firestore_database" "database" {
  project     = "bodor-hospitality-prod"
  name        = "(default)"
  location_id = "eur3"
  type        = "FIRESTORE_NATIVE"
}

resource "google_sql_database_instance" "bodor" {
    name = "bodor-db"
    database_version = "POSTGRES_17"
    region = "europe-west1"

    settings {
        tier = "db-f1-micro"
        availability_type = "ZONAL"
        disk_type = "PD_SSD"
        disk_size = 10
        disk_autoresize = true
    

        backup_configuration {
            enabled = true 
        }

        ip_configuration {
            ipv4_enabled = true

            authorized_networks {
                name  = "home"
                value = "197.244.119.154/32"
            }
            enable_private_path_for_google_cloud_services = true
            private_network= "projects/bodor-hospitality-prod/global/networks/default"
        }
    }
    deletion_protection = true
}

resource "google_sql_database" "database" {
  name     = "bodor"
  instance = google_sql_database_instance.bodor.name
}

resource "google_sql_user" "db_users" {
    name = "taher"
    instance = google_sql_database_instance.bodor.name
    password = "77471580t"
}

module "cloud_run" {
  source = "./modules/cloud_run"

  for_each = local.services

  name     = each.key
  min_instances = each.value.min_instances
  max_instances     = each.value.max_instances
  allow_public = each.value.allow_public
  cloudsql_connection = each.value.cloud_sql_connection
  openia_apikey = var.openia_apikey
}

