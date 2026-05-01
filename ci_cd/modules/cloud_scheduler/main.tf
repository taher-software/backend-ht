resource "google_cloud_scheduler_job" "job" {
  name        = var.name
  description = var.description
  schedule    = var.schedule
  time_zone   = var.time_zone
  region      = var.region

  http_target {
    uri         = var.uri
    http_method = var.http_method

    headers = var.headers
    body = var.body
  }
}