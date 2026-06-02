FROM alpine:3.21

ARG TERRAFORM_VERSION=1.10.3

RUN apk add --no-cache curl unzip \
    && curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
       -o /tmp/terraform.zip \
    && unzip /tmp/terraform.zip -d /usr/local/bin \
    && rm /tmp/terraform.zip \
    && terraform version

WORKDIR /workspace

ENTRYPOINT ["/bin/sh"]
