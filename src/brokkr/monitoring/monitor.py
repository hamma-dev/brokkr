"""
High-level functions to monitor and record sensor and sunsaver status data.
"""

# Standard library imports
import logging
import os
from pathlib import Path
import threading

# Local imports
from brokkr.config.main import CONFIG
import brokkr.output
import brokkr.utils.misc


logger = logging.getLogger(__name__)


def get_status_data(status_data_items=None):
    if status_data_items is None:
        # Only import if needed to avoid dependency on pyserial and pymodbus
        import brokkr.config.monitoring
        status_data_items = brokkr.config.monitoring.STATUS_DATA_ITEMS

    status_data = {}
    for item_name, item_params in status_data_items.items():
        output_data = item_params["function"]()
        if item_params["unpack"]:
            status_data.update(output_data)
        else:
            status_data[item_name] = output_data
    logger.debug("Status data: %s", status_data)
    return status_data


def write_status_data(status_data,
                      output_path=CONFIG["monitor"]["output_path"]):
    output_path = Path(output_path)
    if not output_path.suffix:
        output_path = brokkr.output.determine_output_filename(output_path)
    logger.debug("Writing monitoring output to file: %s",
                 output_path.as_posix())
    brokkr.output.write_line_csv(status_data, output_path)
    return status_data


def start_monitoring(
        output_path=CONFIG["monitor"]["output_path"],
        monitor_interval_s=CONFIG["monitor"]["interval_log_s"],
        sleep_interval=CONFIG["monitor"]["interval_sleep_s"],
        exit_event=None,
        ):
    if exit_event is None:
        exit_event = threading.Event()

    if output_path is not None and not Path(output_path).suffix:
        logger.debug("Ensuring monitoring directory at: %s", output_path)
        os.makedirs(output_path, exist_ok=True)

    while not exit_event.is_set():
        try:
            status_data = get_status_data()
            if output_path is not None:
                write_status_data(status_data, output_path=output_path)
            elif logger.getEffectiveLevel() > logging.DEBUG:
                print("Status data: {}".format(status_data))
        except Exception as e:  # Keep recording data if an error occurs
            logger.critical("%s caught at main level: %s",
                            type(e).__name__, e)
            logger.info("Details:", exc_info=1)
        next_time = (brokkr.utils.misc.monotonic_ns()
                     + monitor_interval_s * 1e9
                     - (brokkr.utils.misc.monotonic_ns()
                        - brokkr.utils.misc.START_TIME)
                     % (monitor_interval_s * 1e9))
        while (not exit_event.is_set()
               and brokkr.utils.misc.monotonic_ns() < next_time):
            exit_event.wait(min(
                [sleep_interval,
                 (next_time - brokkr.utils.misc.monotonic_ns()) / 1e9]))
    exit_event.clear()


def main(verbose=False, **monitor_args):
    if monitor_args.get("output_path", None) is True:
        monitor_args.pop("output_path", None)

    log_args = {"format": "{message}", "style": "{"}
    if verbose and verbose == 1:
        log_args["level"] = logging.INFO
    elif verbose and verbose >= 2:
        log_args["level"] = logging.DEBUG
    else:
        log_args["level"] = logging.WARNING
    logging.basicConfig(**log_args)
    logger.info("Starting Brokkr monitoring...")

    try:
        start_monitoring(**monitor_args)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt recieved; exiting Brokkr...")
