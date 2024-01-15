import requests
import argparse
import dateparser
import datetime
import logging
import os
from bs4 import BeautifulSoup

# some config
media_url = "https://media.xn--fni-snaa.fi"
proflyer_url = media_url + "/proflyer"
debug = False
pbar = None


# TODO: add progressbar


def proflyer_request(cookie):
    # Grab proflyer
    logging.debug("Trying to grab proflyer page")
    try:
        response = requests.get(proflyer_url, headers={"Cookie": cookie})
        return response
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        print("Error on requesting {}".format(proflyer_url))
        raise SystemExit(e)


def set_filter(url, cookie):
    logging.debug("Trying to set filter over url {}".format(media_url + "/" + url))
    try:
        response = requests.get(media_url + "/" + url, headers={"Cookie": cookie})
        return response
    except requests.exceptions.RequestException as e:
        raise SystemExit(e)


def get_video_urls_from_session(session, cookie, perspective):
    logging.info("Getting videos from session {}".format(session["session_time"]))
    response = set_filter(session["filter_url"], cookie)

    logging.info("Parsing HTML Response")
    soup = BeautifulSoup(response.text, "html.parser")
    preview_containers = soup.select_one(
        "#main > div > div:nth-child(2) > div"
    ).find_all("div", class_="media_container_responsive", recursive=False)
    urls = []
    for container in preview_containers:
        container_perspective = container.select_one(
            "div.media_container_responsive > div:nth-child(2) > span"
        ).text.strip()
        if container_perspective == perspective or perspective is None:
            link = container.find("a", class_="btn btn-link download_link")
            if link is not None:
                urls.append(link["href"])

    return urls


def download_sessions(sessions):
    if not os.path.isdir("media"):
        os.mkdir("media")

    for session in sessions:
        logging.info(
            "Downloading {} videos from session {}".format(
                len(session["video_urls"]), session["session_time"]
            )
        )
        date_path = os.path.join("media", session["session_time"].strftime("%Y-%m-%d"))
        session_path = os.path.join(
            date_path, session["session_time"].strftime("%H_%M")
        )

        # create necessary paths
        if not os.path.isdir(date_path):
            os.mkdir(date_path)

        if not os.path.isdir(session_path):
            os.mkdir(session_path)

        for url in session["video_urls"]:
            logging.info("Downloading {}".format(url))
            # not using urlretrieve over requests for file name infos and some header issues
            response = requests.get(url)
            file_name = (
                response.headers["content-disposition"].split("filename=")[1].strip()
            )
            with open(os.path.join(session_path, file_name), "wb") as video:
                video.write(response.content)
            logging.info(
                "Downloaded {} successfully to {}".format(file_name, session_path)
            )


def main():
    # Debug on
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # some config and cli sugar
    parser = argparse.ArgumentParser(description="Download Fööni Videos.")
    parser.add_argument("cookie_file")
    parser.add_argument(
        "--perspective",
        help="Set perspective for downloading. Defaults to all perspectives.",
    )
    parser.add_argument(
        "--start", help="Set start date for downloading. Defaults: today-30days"
    )
    args = parser.parse_args()

    if args.start is None:
        start_date = datetime.date.today() - datetime.timedelta(days=30)
    else:
        start_date = dateparser.parse(args.start)
        if start_date is None:
            raise SystemExit("Start date could not be parsed.")
        start_date -= datetime.timedelta(days=1)

    logging.info("Will fetch valid sessions from {} to today".format(start_date))

    # load cookie file
    with open(args.cookie_file) as f:
        cookie = f.read()

    r = proflyer_request(cookie)
    # grab all available sessions
    valid_sessions = []
    soup = BeautifulSoup(r.text, "html.parser")

    # assuming that finding the first dropdown should be sufficient.
    dropdown = soup.find("ul", attrs={"class": "dropdown-menu"})
    items = dropdown.find_all("li")

    for item in items:
        session_time = dateparser.parse(item.text)
        filter_link = item.find("a")
        if session_time.date() >= start_date:
            valid_sessions.append(
                {
                    "filter_url": filter_link["href"],
                    "session_time": session_time,
                    "video_urls": [],
                }
            )
        # print(item.text)

    logging.info("Found {} valid sessions".format(len(valid_sessions)))

    for session in valid_sessions:
        session["video_urls"] = get_video_urls_from_session(
            session, cookie, args.perspective
        )
        logging.info(
            "Fetched {} video urls for session {}".format(
                len(session["video_urls"]), session["session_time"]
            )
        )

    # TODO: order sessions by date
    download_sessions(valid_sessions)


if __name__ == "__main__":
    main()
