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
                    else: # it's Vimeo, Facebook, or Rumble
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
        skip_button_xpath = "//button[@class='ytp-ad-skip-button ytp-button']"
        player_status = 4
        screenshot_count = 0
        time_0 = time()
        sleep(5)

        # deal with the cookies banner or page only if using the Tor Browser
        if self.controller is not None:
            try:
                reject_button_xpath = "//button[@aria-label='Reject the use of cookies and other data for the purposes described']"
                reject_button = self.driver.find_element(By.XPATH, reject_button_xpath)
                ActionChains(self.driver).click(reject_button).perform()
                wl_log.info('Pressed Reject on cookies banner.')
                sleep(5)
            except:
                try:
                    reject_button_xpath = "//button[@aria-label='Reject all']"
                    reject_button = self.driver.find_element(By.XPATH, reject_button_xpath)
                    ActionChains(self.driver).click(reject_button).perform()
                    wl_log.info('Pressed Reject on cookies page.')
                    sleep(5)
                except:
                    pass

        # try to get an initial player status to see if this Tor
        # exit relay is blocked
        try:
            player_status = self.driver.execute_script(js)
        except WebDriverException:
            wl_log.error('Failed to get player status')
            wl_log.info("Probably on the 'detected unusual traffic' page.")
            return False

        # press play button if necessary
        play_button_xpath = "//button[@aria-label='Play']"
        try:
            play_button = self.driver.find_element(By.XPATH, play_button_xpath)
            ActionChains(self.driver).click(play_button).perform()
            wl_log.info('Pressed play button.')
        except:
            pass
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
            # try to press play again if necessary again
            try:
                play_button = self.driver.find_element(By.XPATH, play_button_xpath)
                ActionChains(self.driver).click(play_button).perform()
                wl_log.info('Pressed play button on subsequent attempt.')
            except:
                pass
            # try to press the skip ad button
            try:
                button = self.driver.find_element(By.XPATH, skip_button_xpath)
                ActionChains(self.driver).click(button).perform()
                wl_log.info("Pressed Skip Ad button.")
            except WebDriverException:
                pass
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
        # initialize time_0 variable here but reset it later
        time_0 = time()

        if 'vimeo' in self.job.url:
            # Vimeo doesn't autoplay, so wait for the Play button to appear and start the video
            wl_log.info("Waiting up to 30 seconds to click the play button.")
            play_button_xpath = "//button[@aria-label='Play']"
            WebDriverWait(self.driver, 30).until(EC.element_to_be_clickable((By.XPATH, play_button_xpath))).click()
            time_0 = time()

        elif 'facebook' in self.job.url:
            # Facebook will autoplay, but we'll wait for some elements to load before we
            # start the clock, so we don't end the capture too early
            wl_log.info("Waiting up to 30 seconds for the Like button to appear.")
            like_button_xpath = "/html/body/div[1]/div/div[1]/div/div[3]/div/div/div/div[1]/div[2]/div[1]/div/div/div[1]/div[2]/div[2]/div/div/div[1]/div/div[1]"
            WebDriverWait(self.driver, 30).until(EC.element_to_be_clickable((By.XPATH, like_button_xpath)))
            time_0 = time()

        elif 'rumble' in self.job.url:
            wl_log.info("Waiting up to 30 seconds for the video player to appear.")
            WebDriverWait(self.driver, 30).until(EC.element_to_be_clickable((By.ID, "videoPlayer")))
            video = self.driver.find_element(By.ID, "videoPlayer")
            ActionChains(self.driver).click(video).perform()
            wl_log.info("Pressed play.")
            time_0 = time()
            sleep(30)
            # deal with Rumble ads which appear in an iframe
            try:
                iframe = self.driver.find_elements(By.TAG_NAME,'iframe')[0]
                self.driver.switch_to.frame(iframe)
                skip_button_xpath = "//button[@aria-label='Skip Ad']"
                skip_button = self.driver.find_element(By.XPATH, skip_button_xpath)
                ActionChains(self.driver).click(skip_button).perform()
                wl_log.info("Pressed Skip Ad button.")
            except:
                pass
            finally:
                self.driver.switch_to.default_content()

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


