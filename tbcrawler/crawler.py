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

    def _do_batch(self):
        """
        Must init/restart the Tor process to have a different circuit.
        If the controller is configured to not pollute the profile, each
        restart forces to switch the entry guard.
        """
        if self.controller is None:
            for self.job.site in range(len(self.job.urls)):
                if len(self.job.url) > cm.MAX_FNAME_LENGTH:
                    wl_log.warning("URL is too long: %s" % self.job.url)
                    continue
                self._do_instance()
                sleep(float(self.job.config['pause_between_videos']))
        else:
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
            wl_log.info("*** Visit %s to %s ***", self.job.visit, self.job.url)
            wl_log.info("*** Expected playback time is %s seconds ***", self.job.playback_time)
            self.job.screen_num = 0
            with self.driver.launch():
                try:
                    self.driver.set_page_load_timeout(cm.SOFT_VISIT_TIMEOUT)
                except WebDriverException as seto_exc:
                    wl_log.error("Setting soft timeout %s", seto_exc)
                visit_successful = self._do_visit()
                if not visit_successful:
                    ut.delete_dir(self.job.path)
                    return
            sleep(float(self.job.config['pause_between_loads']))

    def _do_visit(self):
        with Sniffer(path=self.job.pcap_file, filter=cm.DEFAULT_FILTER,
                     device=self.device, dumpcap_log=self.job.pcap_log):
            try:
                with ut.timeout(cm.HARD_VISIT_TIMEOUT):
                    # begin loading page
                    self.driver.get(self.job.url)
                    if 'youtube' in self.job.url:
                        return self._visit_youtube()
                    else: # it's Vimeo, Dailymotion, or Rumble
                        return self._visit_other()
            except (cm.HardTimeoutException, TimeoutException):
                wl_log.error("Visit to %s reached hard timeout!", self.job.url)
                return False
            except Exception as exc:
                wl_log.error("Unknown exception: %s", exc)
                return False

    def _visit_youtube(self):
        status_to_string = ['ended', 'playing', 'paused', 'buffering', 'none', 'queued', 'unstarted']
        js = "return document.getElementById('movie_player').getPlayerState()"
        player_status = 4
        screenshot_count = 0
        sleep(5)

        # deal with the cookies banner only if using the Tor Browser
        if self.controller is not None:
            wl_log.info('Trying to reject cookies.')
            ActionChains(self.driver).send_keys(Keys.TAB * 4 + Keys.ENTER).perform()
            sleep(5)

        # press play for both Tor Browser and Firefox
        wl_log.info('Trying to press play.')
        ActionChains(self.driver).send_keys('k').perform()
        time_0 = time()
        sleep(20)

        # try to get an initial player status to see if this Tor
        # exit relay is blocked
        try:
            wl_log.info('Trying to get initial player status.')
            player_status = self.driver.execute_script(js)
        except WebDriverException:
            wl_log.error('Failed to get player status')
            wl_log.info("Probably on the 'detected unusual traffic' page.")
            return False

        # if it's still unstarted, we're watching an ad,
        # so let's skip it if possible like a human would do
        if player_status == -1:
            wl_log.info("Must be an ad. We'll try to skip it.")
            # screenshot of the ad and skip button (or lack of one)
            if self.screenshots:
                wl_log.info("Trying to take a screenshot.")
                try:
                    self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                    screenshot_count += 1
                except WebDriverException:
                    wl_log.error("Cannot get screenshot.")
            try:
                skip_button_xpath = "//button[@class='ytp-ad-skip-button ytp-button']"
                self.driver.find_element(By.XPATH, skip_button_xpath).click()
            except WebDriverException:
                wl_log.error("Can't skip the ad.")
            sleep(5)
            player_status = self.driver.execute_script(js)
            wl_log.debug('Updated player status: {}'
                         .format(status_to_string[player_status]))

        # starting screenshot
        if self.screenshots:
            wl_log.info("Trying to take a screenshot.")
            try:
                self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                screenshot_count += 1
            except WebDriverException:
                wl_log.error("Cannot get screenshot.")

        while True:
            loaded_fraction = self.driver.execute_script("return document.getElementById('movie_player').getVideoLoadedFraction()")
            wl_log.debug('Fraction of video loaded: ' + str(loaded_fraction))
            # end when the video should end, or after 6 minutues, whichever is sooner
            elapsed_time = time() - time_0
            if elapsed_time > self.job.playback_time - 10 or elapsed_time > 360:
                # ending screenshot
                if self.screenshots:
                    wl_log.info("Trying to take a screenshot.")
                    try:
                        self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                        screenshot_count += 1
                    except WebDriverException:
                        wl_log.error("Cannot get screenshot.")
                wl_log.info("Ending successful visit after " + str(time() - time_0) + " seconds.")
                return True
            sleep(10)

    def _visit_other(self):
        screenshot_count = 0

        if 'vimeo' in self.job.url:
            # Vimeo doesn't autoplay, so wait for the Play button to appear and start the video
            wl_log.info("Waiting up to 30 seconds to click the play button.")
            play_button_xpath = "//button[@aria-label='Play']"
            WebDriverWait(self.driver, 30).until(EC.element_to_be_clickable((By.XPATH, play_button_xpath))).click()

        elif 'dailymotion' in self.job.url:
            # Dailymotion will autoplay, but we'll wait for some elements to load before we
            # start the clock, so we don't end the capture too early
            wl_log.info("Waiting up to 30 seconds for the Like button to appear.")
            like_button_xpath = "/html/body/div[1]/div/main/div[1]/div/div/div[1]/div/div[2]/div/div/div/div[1]/div[5]/div/div/button[1]"
            WebDriverWait(self.driver, 30).until(EC.element_to_be_clickable((By.XPATH, like_button_xpath)))

        elif 'rumble' in self.job.url:
            wl_log.info("Waiting up to 30 seconds for the video player to appear.")
            WebDriverWait(self.driver, 30).until(EC.element_to_be_clickable((By.ID, "videoPlayer")))
            video = self.driver.find_element(By.ID, "videoPlayer")
            wl_log.info("Pressing play.")
            ActionChains(self.driver).click(video).perform()
            sleep(30)
            # screenshot of the ad and skip button (or lack of one)
            if self.screenshots:
                wl_log.info("Trying to take a screenshot.")
                try:
                    self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                    screenshot_count += 1
                except WebDriverException:
                    wl_log.error("Cannot get screenshot.")
            # deal with Rumble ads which appear in an iframe
            try:
                wl_log.info("Trying to skip ad if possible.")
                iframe = self.driver.find_elements(By.TAG_NAME,'iframe')[0]
                self.driver.switch_to.frame(iframe)
                skip_button_xpath = "//button[@aria-label='Skip Ad']"
                skip_button = self.driver.find_element(By.XPATH, skip_button_xpath)
                ActionChains(self.driver).click(skip_button).perform()
            except WebDriverException:
                wl_log.error("No ad playing, or can't skip it.")
            finally:
                self.driver.switch_to.default_content()

        time_0 = time()
        sleep(3)
        # starting screenshot
        if self.screenshots:
            wl_log.info("Trying to take a screenshot.")
            try:
                self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                screenshot_count += 1
            except WebDriverException:
                wl_log.error("Cannot get screenshot.")
        while True:
            wl_log.debug('Heartbeat.')
            # end when the video should end, or after 6 minutues, whichever is sooner
            elapsed_time = time() - time_0
            if elapsed_time > self.job.playback_time - 10 or elapsed_time > 360:
                # ending screenshot
                if self.screenshots:
                    wl_log.info("Trying to take a screenshot.")
                    try:
                        self.driver.get_screenshot_as_file(self.job.png_file(screenshot_count))
                        screenshot_count += 1
                    except WebDriverException:
                        wl_log.error("Cannot get screenshot.")
                wl_log.info("Ending successful visit after " + str(time() - time_0) + " seconds.")
                return True
            sleep(10)

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


