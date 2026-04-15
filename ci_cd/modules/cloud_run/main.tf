resource "google_cloud_run_service" "service" {
    name = var.name
    location = "europe-west1"
    template {

        metadata {
            annotations = {
                "autoscaling.knative.dev/minScale" = var.min_instances
                "autoscaling.knative.dev/maxScale" = var.max_instances
                "run.googleapis.com/cloudsql-instances" = var.cloudsql_connection
                "terraform-redeploy" = timestamp()
            }
        }
        spec {
            container_concurrency = 80
            containers {
                image = "77471580t/bodor_web_app:latest"
                resources {
                    limits = {
                        cpu    = "1"
                        memory = "512Mi"
                    }
                }
                ports {
                    container_port = 8080
                }

                env {
                    name = "db_url"
                    value = var.db_url
                }

                env {
                    name = "DB_NAME"
                    value = var.DB_NAME
                }

                env {
                    name = "DB_USER"
                    value = var.DB_USER
                }

                env {
                    name = "DB_PASSWORD"
                    value = var.DB_PASSWORD
                }

                env {
                    name = "mail_username"
                    value = var.mail_username
                }

                env {
                    name = "mail_pwd"
                    value = var.mail_pwd
                }

                env {
                    name = "application_url"
                    value = var.application_url
                }

                env {
                    name = "jwt_access_expires"
                    value = var.jwt_access_expires
                }

                env {
                    name = "jwt_algorithm"
                    value = var.jwt_algorithm
                }

                env {
                    name = "jwt_secret"
                    value = var.jwt_secret
                }

                env {
                    name = "openia_apikey"
                    value = var.openia_apikey
                }

                env {
                    name = "super_admin_emails"
                    value = var.super_admin_emails
                }

                env {
                    name = "worker_url"
                    value = var.worker_url
                }

                env {
                    name = "app_store_app_name"
                    value = var.app_store_app_name
                }

                env {
                    name = "play_store_app_name"
                    value = var.play_store_app_name
                }

                env {
                    name = "app_store_url"
                    value = var.app_store_url
                }

                env {
                    name = "play_store_url"
                    value = var.play_store_url
                }

                env {
                    name = "commercial_email_list"
                    value = var.commercial_email_list 
                }
            }
            
        }
    }
    traffic {
        percent = 100
        latest_revision = true
    }
}

resource "google_cloud_run_service_iam_member" "public" {
  count = var.allow_public ? 1 : 0

  service  = google_cloud_run_service.service.name
  location = google_cloud_run_service.service.location

  role   = "roles/run.invoker"
  member = "allUsers"
}

resource "google_project_iam_member" "cloud_run_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${var.service_account_email}"
}