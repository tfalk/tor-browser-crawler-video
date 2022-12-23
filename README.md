tor-browser-crawler-video
===============

This is a fork of the [tor-browser-crawler](https://github.com/webfp/tor-browser-crawler).
The original fork was by Nate Mathews. Danny Campuzano forked it from him. I forked it from Danny to update it for YouTube's interface in late 2022. I'm running Ubuntu 22.04 on a VM with 2 CPUs and 1 GB of RAM.

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
2. Install Tor

`sudo apt install tor`

Change `RUN_DAEMON="yes"` to `RUN_DAEMON="no"` in `/etc/default/tor`

`systemctl stop tor`

3. Build the Docker container
```
sudo apt install make
sudo make build
```
4. Setup your crawl configuration files
    * replace the contents of videos.txt with your list of YouTube URLs to crawl
    * edit Makefile to use the correct network interface (find yours with `ip link`)
    * if you're crawling long videos, adjust the `--timeout` value in Makefile
    * make any desired changes to config.ini
5. Start the crawl
    * `make run` launches a container and starts crawling
    * the logs, packet captures, and screenshots appear in the `results` directory

## Notes
* Library Versions
    * most of the modules listed in requirements.txt are the last versions that supported Python 2.7
    * this project was originally frozen to v8.0.2 of the TBB, and I've changed it to v12.0.1
    * to use another TBB version, change the version number in Dockerfile and do another `sudo make build`
    * leaving the version number blank to get the latest version of TBB no longer works

* About 50% of the time, YouTube will serve up a page saying `detected unusual traffic` and you can't get around it until you build another Tor 
circuit with a new exit relay. The other 50% of the time, you'll get a `Before you continue to YouTube` banner about cookies once the page finally loads,  preventing more than about 6 MB of the video from loading and playing, so much of the logic in crawler.py that I'm changing deals with this. Very rarely, the video does just load and start on autoplay without intervention.

* I changed the trigger for when to end a packet capture. It used to be when the player status was `ended` but now it looks for when the video is fully loaded, even though the video itself is still playing. This is because we're only interested in the network traffic.

* The default Docker settings often resulted in a Selenium WebDriverException saying `failed to decode response from marionette` and subsequently `tried to run command without establishing a connection` when trying to run execute_script() commands even though the page and video were loading. The fix was to give the container higher runtime constraints on resources, specifically memory and shared host memory (see https://stackoverflow.com/questions/49734915/failed-to-decode-response-from-marionette-message-in-python-firefox-headless-s). This is included in the `run` command in Makefile
