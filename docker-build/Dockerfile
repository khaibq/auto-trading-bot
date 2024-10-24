FROM public.ecr.aws/k3w6z9a4/python-lambda/dydx-template:latest
ARG FUNCTION_DIR="/app"
# Copy function code
RUN mkdir -p ${FUNCTION_DIR}
COPY *.py ${FUNCTION_DIR}/
