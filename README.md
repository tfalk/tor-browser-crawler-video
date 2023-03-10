tor-browser-crawler-video
===============

This is a fork of the [tor-browser-crawler](https://github.com/webfp/tor-browser-crawler).
The original fork was by Nate Mathews. Danny Campuzano forked it from him. I forked it from Danny to update it for the YouTube, Dailymotion, Vimeo, and Rumble interfaces in late 2022, early 2023, and add functionality to crawl the same platforms without using Tor. I'm running an Ubuntu Server 22.04 VM with 2 CPUs and 1 GB of RAM.

#### Steps
1. Install Docker
```
sudo apt-get install ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
sudo systemctl enable docker.service
systemctl disable containerd.service
```

2. Logout, login, then build and run the Docker container
```
sudo apt install make
make build
```
3. Setup your crawl configuration files
    * replace the contents of videos.txt with your list of YouTube, Dailymotion, Vimeo, and Rumble URLs to crawl, followed by a comma and the duration in seconds
    * edit Makefile to use the correct network interface (find yours with `ip link`)
    * if you're crawling long videos, adjust the `--timeout` value in Makefile
    * make any desired changes to config.ini
4. Start the crawl
    * `make run` launches a container and starts crawling with the Tor Browser
    * `make run-without-tor` starts crawing with Firefox ESR without Tor
    * the logs, packet captures, and screenshots appear in the `results` directory

## Notes
* Software and Library Versions
    * This project was originally frozen to v8.0.2 of the TBB, and I've updated it to v12.0.3 with geckodriver v0.32.2
    * I've changed the Docker base image from python:2.7 to debian:sid-slim for the latest Python3 and selenium, tbselenium, etc. packages
    * Debian Sid also provides the latest Firefox ESR and uBlock Origin for the `run-without-tor` option
    * To use another TBB version, change the version number in Dockerfile and do another `make build`
    * Leaving the version number blank to get the latest version of TBB no longer works

* I've changed the triggers for when to end a packet capture. For YouTube, it used to be when the player status was `ended`, and then when the fraction of the video loaded 
reached 1. Now, for all platforms, it ends after the expected playback duration of the video or after 6 minutes, whichever is shorter. It also ends early if it can't get an 
initial status from the YouTube player (usually because the Tor exit relay is blocked) or if it doesn't see certain page elements (depending on the platform) within 30 seconds, 
in which cases it just deletes the whole subdirectory in `results` for that visit.

* About 30% of the time when using the Tor Browser, YouTube will serve a page saying `detected unusual traffic`. The other 70% of the time, it will show a `Before you continue 
to YouTube` banner about cookies, preventing more than about 6 MB of the video from loading. The crawler rejects cookies, and then the video autoplays. Without Tor, the cookie 
banner doesn't appear but the crawler needs to press play. If playback is still `unstarted` at that point, it's because an ad is playing, so the crawler tries skipping the ad(s) 
like a human would do after waiting 15 seconds.

* Dailymotion and Vimeo don't show many ads when using the Tor Browser. Dailymotion will autoplay, but the crawler needs to press play on Vimeo. Rumble requires the crawler to 
press play, and it shows a lot of ads (even with uBlock Origin for the `run-without-tor` option), which the crawler tries to skip like a human would do after waiting 15 seconds.

* I've set the `--snapshot-length` to 71 bytes for tcpdump, so it only saves the Ethernet, IP, and TCP headers and TLS record lengths. We need these for our analysis depending 
on the threat model used. We don't need the encrypted payloads for anything, and they would require orders-of-magnitude more storage space.

* Using the `run-without-tor` option, YouTube streams video over the QUIC protocol, so I've changed the tcpdump filter to capture UDP in addition to TCP.

* The default Docker settings often resulted in a Selenium WebDriverException saying `failed to decode response from marionette` and subsequently `tried to run command without 
establishing a connection` when trying to run execute_script() commands even though the page and video were loading. The fix was to give the container higher runtime constraints 
on resources, specifically memory and shared host memory (see 
https://stackoverflow.com/questions/49734915/failed-to-decode-response-from-marionette-message-in-python-firefox-headless-s). This is included in the `run` command in Makefile
