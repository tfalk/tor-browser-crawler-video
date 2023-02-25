# This dockerfile allows to run an crawl inside a docker container

# Pull base image.
#FROM debian:stable-slim
FROM python:3.11

# Install required packages.
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --yes install sudo build-essential autoconf git zip unzip xz-utils
RUN DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --yes install libtool libevent-dev libssl-dev
RUN DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --yes install python-setuptools
RUN DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --yes install net-tools ethtool tshark libpcap-dev iw tcpdump
RUN DEBIAN_FRONTEND=noninteractive apt-get --assume-yes --yes install xvfb firefox-esr
RUN apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

# move tcpdump per the workaround for an error discussed here
# https://stackoverflow.com/questions/30663245/tcpdump-reports-error-in-docker-container-thats-started-with-privileged
RUN mv /usr/bin/tcpdump /usr/sbin/tcpdump

# Install python requirements.
RUN pip install --upgrade pip
COPY requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

# add host user to container
RUN adduser --system --group --disabled-password --gecos '' --shell /bin/bash docker

# download geckodriver
ADD https://github.com/mozilla/geckodriver/releases/download/v0.32.2/geckodriver-v0.32.2-linux64.tar.gz /bin/
RUN tar -zxvf /bin/geckodriver* -C /bin/
ENV PATH /bin/geckodriver:$PATH

# add setup.py
RUN git clone https://gist.github.com/timwalsh300/e611e4e18e4e5911eee0b3252318804d.git /home/docker/tbb_setup
RUN python3 /home/docker/tbb_setup/setup.py 12.0.3

# Set the display
ENV DISPLAY $DISPLAY

# Change directory
WORKDIR /home/docker/tbcrawl
