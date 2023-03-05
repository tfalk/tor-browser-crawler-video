tor-browser-crawler-video
===============

This is a fork of the [tor-browser-crawler](https://github.com/webfp/tor-browser-crawler).
The original fork was by Nate Mathews. Danny Campuzano forked it from him. I forked it from Danny to update it for the YouTube, Vimeo, and Dailymotion interfaces in late 2022, early 2023, and add functionality to crawl the same platforms without using Tor. I'm running Ubuntu Server 22.04 on a VM with 2 CPUs and 1 GB of RAM.

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

2. Build the Docker container
```
sudo apt install make
sudo make build
```
3. Setup your crawl configuration files
    * replace the contents of videos.txt with your list of YouTube, Vimeo, and Dailymotion URLs to crawl, followed by a comma and the duration in seconds
    * edit Makefile to use the correct network interface (find yours with `ip link`)
    * if you're crawling long videos, adjust the `--timeout` value in Makefile
    * make any desired changes to config.ini
4. Start the crawl
    * `sudo make run` launches a container and starts crawling with the Tor Browser
    * `sudo make run-without-tor` starts crawing with Firefox ESR without Tor
    * the logs, packet captures, and screenshots appear in the `results` directory

## Notes
* Software and Library Versions
    * I've updated everything from Python 2.7 to 3.11 and the latest selenium, tbselenium, and geckodriver
    * This project was originally frozen to v8.0.2 of the TBB, and I've updated it to v12.0.3
    * To use another TBB version, change the version number in Dockerfile and do another `sudo make build`
    * Leaving the version number blank to get the latest version of TBB no longer works

* About 30% of the time when using the Tor Browser, YouTube will serve up a page saying `detected unusual traffic` and you can't get around it until Tor attaches streams to another 
circuit with a different exit relay (this was more like 50% when using the older TBB v8.0.2). The other 70% of the time, you'll get a `Before you continue to YouTube` banner about cookies once the page finally loads, preventing more than about 6 MB of the video from loading. The logic in crawler.py handles the cookie pop-up and then presses play if necessary to get video playback started. If playback is still "unstarted" at that point, it's because an ad is playing before the video. Even if we skipped the ad, loading it has already polluted the packet capture, so we just abort the visit. We need clean training data.

* For Vimeo, about 20% of the time, the crawler hits a hard 60-second timeout while waiting for the video player to load. It seems random. The other 80% of the time, the player loads OK and we start playing the video before a pop-up prompting us to authenticate with Google steals the focus.

* I've changed the triggers for when to end a packet capture. For YouTube, it used to be when the player status was `ended` but now it will look for when the video is fully loaded, even though the video itself is still playing. This speeds up crawling, and we're only interested in the network traffic anyway. If it can't get an initial player status within the first 20 seconds, that will also terminate the visit instead of waiting for the hard timeout. For Vimeo and Dailymotion, the trigger for when to end a packet capture is the elapsed time after the player loads and the video starts. Vimeo appears to buffer about 20 seconds of video, so when we're less than 20 seconds from the end of the playback time (specified in videos.txt, assuming it plays smoothly) we end the capture before another video gets queued up.

* I've added logic that deletes the whole directory for a visit after hitting YouTube's "unusual activity detected" page, after aborting due to ads, or after a hard timeout, so we only store what we'll actually want to parse later.

* I've set the `--snapshot-length` to 71 bytes for tcpdump, so we only save the Ethernet, IP, and TCP headers and TLS record lengths. We need these for our analysis depending on the threat model used. We don't need the encrypted payloads for anything. This reduces required storage space by roughly 95%.

* Using the run-without-tor option, I'm seeing YouTube stream video over the QUIC protocol, so I've changed the tcpdump filter to capture UDP in addition to TCP.

* The default Docker settings often resulted in a Selenium WebDriverException saying `failed to decode response from marionette` and subsequently `tried to run command without establishing a connection` when trying to run execute_script() commands even though the page and video were loading. The fix was to give the container higher runtime constraints on resources, specifically memory and shared host memory (see https://stackoverflow.com/questions/49734915/failed-to-decode-response-from-marionette-message-in-python-firefox-headless-s). This is included in the `run` command in Makefile
