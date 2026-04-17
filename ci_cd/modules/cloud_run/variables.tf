variable "name" {}

variable "db_url" {
    type = string 
    default = "postgresql+psycopg2://taher:77471580t@/bodor?host=/cloudsql/bodor-hospitality-prod:europe-west1:bodor-db"
}

variable "DB_NAME" {
    type = string 
    default = "bodor"
}

variable "DB_USER" {
    type = string 
    default = "taher"
}

variable "DB_PASSWORD" {
    type = string
    default = "77471580t"
}

variable "mail_username" {
    type = string
    default = "ttaherhagui@gmail.com"
}
            
variable "mail_pwd" {
    type = string
    default = "jqlq vczg qgtj kobj"
}

variable "application_url" {
    type = string
    default = "https://bodor-hospitality-prod.ew.r.appspot.com/"
}
           
variable "jwt_access_expires" {
    type = string
    default = 14400
}

variable "jwt_secret" {
    type = string
    default = "taher"
}

variable "openia_apikey" {
    type = string
    default = ""
} 

variable "super_admin_emails" {
    type = string
    default = "ttaherhagui@gmail.com"
}

variable "worker_url" {
    type = string
    default = "https://worker-bodor-368726253523.europe-west1.run.app"
}          


variable "app_store_app_name" {
    type = string
    default = "Bodor"
}

variable "play_store_app_name" {
    type = string
    default = "Bodor"
}

variable "app_store_url" {
    type = string
    default = "https://www.cartdna.com/what-is-my-shopify-url"
}


variable "play_store_url" {
    type = string
    default = "https://www.cartdna.com/what-is-my-shopify-url"
}

variable "commercial_email_list" {
    type = string
    default = "ttaherhagui@gmail.com"
}

variable "min_instances" {}

variable "max_instances" {}

variable "cloudsql_connection" {}

variable "allow_public" {
    type = bool
    default = false
}

variable "jwt_algorithm" {
    type = string
    default = "HS256"
}

variable "project_id" {
    type = string 
    default = "bodor-hospitality-prod"
}

variable "service_account_email" {
    type = string
    default = "368726253523-compute@developer.gserviceaccount.com"
}

           