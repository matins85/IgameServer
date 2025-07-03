ARG PYTHON_VERSION=3.9-slim

FROM python:${PYTHON_VERSION}

# System env settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create app directory
WORKDIR /code

# Install pipenv & dependencies
RUN pip install pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv install --deploy --system

# Copy project files
COPY . .

EXPOSE 8000

# Run with Daphne (ASGI support)
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "igame.asgi:application"]
