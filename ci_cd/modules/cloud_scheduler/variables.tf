variable "name" {}
variable "time_zone" {
    default = "Africa/Tunis"
}
variable "description" {}
variable "schedule" {}
variable "region" {
    default = "europe-west1"
}
variable "uri" {}
variable "http_method" {
    default = "POST"
}
variable "headers" {
    type = map(string)
    default= {
        "Content-Type" = "application/json"
    }
}
variable "body" {
    default = null
}