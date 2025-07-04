FROM python:3.13

WORKDIR /usr/src/app

# Limit what we copy to keep image size down.
# We only need the src/ folder and the pyproject.toml file.
COPY pyproject.toml src ./

# Build and then install the gamatrix package only.
RUN python -m pip install -U pip && \
    python -m pip install build && \
    python -m build --wheel && \
    python -m pip install dist/gamatrix-*.whl && \
    # Clean up work folder
    rm -rf /usr/src/app/* && \
    # Create config and data directories mounted in the Docker run command. (See README for details).
    mkdir /usr/src/app/gog_dbs /usr/src/app/config

# This is used by "just dev"
RUN echo '[ -e /root/.bashrc.user ] && . /root/.bashrc.user' >> /root/.bashrc

CMD [ "python", "-m", "gamatrix", "-c", "/usr/src/app/config.yaml", "-p", "80", "-s" ]
