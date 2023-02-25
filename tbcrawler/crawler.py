import sys
from os.path import join, split
from pprint import pformat
from time import sleep, time

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

import tbcrawler.common as cm
import tbcrawler.utils as ut
from tbcrawler.dumputils import Sniffer
from tbcrawler.log import wl_log

class VideoCrawler(object):
    def __init__(self, driver, controller, screenshots=True, device="eth0"):
        self.driver = driver
        self.controller = controller
        self.screenshots = screenshots
        self.device = device
        self.job = None

    def crawl(self, job):
        """Crawls a set of urls in batches."""
        self.job = job
        wl_log.info("Starting new crawl")
        wl_log.info(pformat(self.job))
        for self.job.batch in range(self.job.batches):
            wl_log.info("**** Starting batch %s ***" % self.job.batch)
            self._do_batch()
            sleep(float(self.job.config['pause_between_batches']))

    def post_visit(self):
        guard_ips = set([ip for ip in self.controller.get_all_guard_ips()])
        wl_log.debug("Found %s guards in the consensus.", len(guard_ips))
        wl_log.info("Filtering packets without a guard IP.")
        try:
            ut.filter_pcap(self.job.pcap_file, guard_ips)
        except Exception as e:
            wl_log.error("ERROR: filtering pcap file: %s.", e)
            wl_log.error("Check pcap: %s", self.job.pcap_file)

    def _do_batch(self):
        """
        Must init/restart the Tor process to have a different circuit.
        If the controller is configured to not pollute the profile, each
        restart forces to switch the entry guard.
        """
        with self.controller.launch():
            for self.job.site in range(len(self.job.urls)):
                if len(self.job.url) > cm.MAX_FNAME_LENGTH:
                    wl_log.warning("URL is too long: %s" % self.job.url)
                    continue
                self._do_instance()
                sleep(float(self.job.config['pause_between_videos']))

    def _do_instance(self):
        for self.job.visit in range(self.job.visits):
            ut.create_dir(self.job.path)
            wl_log.info("*** Visit #%s to %s ***", self.job.visit, self.job.url)
            self.job.screen_num = 0
            with self.driver.launch():
                try:
                    self.driver.set_page_load_timeout(cm.SOFT_VISIT_TIMEOUT)
                except WebDriverException as seto_exc:
                    wl_log.error("Setting soft timeout %s", seto_exc)
                self._do_visit()
            sleep(float(self.job.config['pause_between_loads']))
            self.post_visit()

    def _do_visit(self):
        with Sniffer(path=self.job.pcap_file, filter=cm.DEFAULT_FILTER,
                     device=self.device, dumpcap_log=self.job.pcap_log):
            sleep(1)  # make sure tcpdump is running
            try:
                with ut.timeout(cm.HARD_VISIT_TIMEOUT):
                    # begin loading page
                    self.driver.get(self.job.url)
                    if 'youtube' in self.job.url:
                        self._visit_youtube()
                    else: # it's Vimeo or Dailymotion
                        self._visit_vimeo_or_dailymotion()
            except (cm.HardTimeoutException, TimeoutException):
                wl_log.error("Visit to %s reached hard timeout!", self.job.url)
            except Exception as exc:
                wl_log.error("Unknown exception: %s", exc)

    def _visit_youtube(self):
        status_to_string = ['ended', 'playing', 'paused', 'buffering', 'none', 'queued', 'unstarted']
        js = "return document.getElementById('movie_player').getPlayerState()"
        player_status = 4
        time_0 = time()
        time_now = time_0
        time_last_checks = time_0 - 30
        screenshot_count = 0

        # try a few times to get an initial player status
        while player_status == 4:
            time_now = time()
            try:
                wl_log.info('Trying to get initial player status.')
                player_status = self.driver.execute_script(js)
            except WebDriverException as e:
                wl_log.error('Failed to get player status')
                if time_now - time_0 > 20:
                    wl_log.info('Terminating visit after the third try.')
                    wl_log.info('Probably on the \'detected unusual traffic\' page.')
                    if self.screenshots:
                        wl_log.info('Trying to take a screenshot.')
                        try:
                            self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                        except WebDriverException as e:
                            wl_log.error('Cannot get screenshot.')
                    return
                sleep(10)

        # continue the visit capture until the video has fully loaded
        loaded_fraction = 0
        while loaded_fraction < 1:
            time_now = time()
            # check progress on the screenshot interval
            if time_now - time_last_checks > cm.SCREENSHOT_INTERVAL:
                try:
                    player_status = self.driver.execute_script(js)
                    wl_log.debug('Player status: {} at {:.2f} seconds'
                                 .format(status_to_string[player_status], time_now - time_0))
                except Exception as e:
                    wl_log.error('Failed to get player status at 30-second interval.')
                # try a few things if the video isn't playing
                if player_status == -1 or player_status == 2:
                    try:
                        # accept all cookies
                        wl_log.info('Trying to accept cookies.')
                        ActionChains(self.driver).send_keys(Keys.TAB * 5 + Keys.ENTER).perform()
                        sleep(5)
                        player_status = self.driver.execute_script(js)
                    except WebDriverException as e:
                        wl_log.error(str(e))
                if player_status == -1 or player_status == 2:
                    try:
                        # press play
                        wl_log.info('Trying to press play.')
                        ActionChains(self.driver).send_keys('k').perform()
                        sleep(5)
                        player_status = self.driver.execute_script(js)
                    except WebDriverException as e:
                        wl_log.error(str(e))
                if player_status == -1 or player_status == 2:
                    try:
                        # skip ad
                        wl_log.info('Trying to skip ads.')
                        skip_button_xpath = "//button[@class=\"ytp-ad-skip-button ytp-button\"]"
                        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, skip_button_xpath))).click()
                        sleep(5)
                        player_status = self.driver.execute_script(js)
                    except WebDriverException as e:
                        wl_log.error(str(e))
                # take periodic screenshot
                if self.screenshots:
                    try:
                        self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                        screenshot_count += 1
                    except WebDriverException:
                        wl_log.error('Cannot get screenshot.')
                # get the fraction of the video loaded now, hopefully with initial ads skipped
                try:
                    loaded_fraction = self.driver.execute_script("return document.getElementById('movie_player').getVideoLoadedFraction()")
                    wl_log.debug('youtube video loaded fraction: ' + str(loaded_fraction))
                except WebDriverException:
                    wl_log.error(str(e))
                time_last_checks = time_now

    def _visit_vimeo_or_dailymotion(self):
        if 'vimeo' in self.job.url:
            # Vimeo doesn't autoplay, so wait for the Play button to appear and start the video
            wl_log.info("Waiting up to 60 seconds for the Play button to appear.")
            play_button_xpath = "//button[@aria-label='Play']"
            WebDriverWait(self.driver, 60).until(EC.element_to_be_clickable((By.XPATH, play_button_xpath)))
            wl_log.info("Pressing spacebar to start the video.")
            ActionChains(self.driver).send_keys(Keys.SPACE).perform()
        elif 'dailymotion' in self.job.url:
            # Dailymotion will autoplay, but we'll wait for some elements to load before we
            # start the clock, so we don't end the capture too early
            wl_log.info("Waiting up to 60 seconds for the cookie policy to appear.")
            understand_button_xpath = "/html/body/div[1]/div/div[2]/button"
            WebDriverWait(self.driver, 60).until(EC.element_to_be_clickable((By.XPATH, understand_button_xpath)))
        # take a screenshot and then repeat every 20 seconds
        # until the expected time required has elapsed
        time_0 = time()
        screenshot_count = 0
        while True:
            if self.screenshots:
                wl_log.info("Trying to take a screenshot.")
                try:
                    self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                    screenshot_count += 1
                except WebDriverException:
                    wl_log.error("Cannot get screenshot.")
            sleep(20)
            # Vimeo buffers about 20 seconds of the stream,
            # so we can stop once we're less than 20 seconds
            # from the end of playback
            if time() - time_0 > self.job.playback_time - 20:
                wl_log.info("Ending after the expected playback time of about " + str(self.job.playback_time) + " seconds.")
                return

class CrawlJob(object):
    def __init__(self, config, urls):
        self.urls = urls
        self.visits = int(config['visits'])
        self.batches = int(config['batches'])
        self.config = config

        # state
        self.site = 0
        self.visit = 0
        self.batch = 0

    @property
    def pcap_file(self):
        return join(self.path, "capture.pcap")

    @property
    def pcap_log(self):
        return join(self.path, "dump.log")

    @property
    def instance(self):
        return self.batch * self.visits + self.visit

    @property
    def url(self):
        return self.urls[self.site][0]

    @property
    def playback_time(self):
        return self.urls[self.site][1]

    @property
    def path(self):
        attributes = [self.batch, self.site, self.instance]
        return join(cm.CRAWL_DIR, "_".join(map(str, attributes)))

    def png_file(self, time):
        return join(self.path, "screenshot_{}.png".format(time))

    def __repr__(self):
        return "Batches: %s, Sites: %s, Visits: %s" \
               % (self.batches, len(self.urls), self.visits)


