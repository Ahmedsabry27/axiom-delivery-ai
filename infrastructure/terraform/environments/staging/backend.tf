terraform {
  backend "s3" {
    bucket       = "axiom-delivery-ai-594677690649-eu-west-2-tfstate"
    key          = "staging/terraform.tfstate"
    region       = "eu-west-2"
    profile      = "default"
    encrypt      = true
    use_lockfile = true
  }
}
