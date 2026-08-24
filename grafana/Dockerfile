FROM grafana/grafana:13.1.0

COPY provisioning /etc/grafana/provisioning
COPY dashboards /var/lib/grafana/dashboards

ENV GF_SECURITY_ADMIN_USER=admin
ENV GF_SECURITY_ADMIN_PASSWORD=admin123

EXPOSE 3000