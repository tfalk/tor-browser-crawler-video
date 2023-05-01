# Pull base image.
# Debian Bookworm gets us a farily up-to-date version of everything and
# a few years of stability, and slim saves disk space by excluding a
# lot packages that we don't need
FROM debian:bookworm-slim

# Install required packages.
RUN apt-get update
RUN apt-get --yes install git python3-pip python3-setuptools tcpdump xvfb firefox-esr webext-ublock-origin-firefox
RUN apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

# move tcpdump per the workaround for an error discussed here
# https://stackoverflow.com/questions/30663245/tcpdump-reports-error-in-docker-container-thats-started-with-privileged
RUN mv /usr/bin/tcpdump /usr/sbin/tcpdump

# Install python requirements.
COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt --break-system-packages

# add host user to container
RUN adduser --system --group --disabled-password --gecos '' --shell /bin/bash docker

# download geckodriver
ADD https://github.com/mozilla/geckodriver/releases/download/v0.32.2/geckodriver-v0.32.2-linux64.tar.gz /bin/
RUN tar -zxvf /bin/geckodriver* -C /bin/
ENV PATH /bin/geckodriver:$PATH

# add setup.py
RUN git clone https://gist.github.com/timwalsh300/e611e4e18e4e5911eee0b3252318804d.git /home/docker/tbb_setup
RUN python3 /home/docker/tbb_setup/setup.py 12.0.5

# Set the display
ENV DISPLAY $DISPLAY

# Change directory
WORKDIR /home/docker/tbcrawl
