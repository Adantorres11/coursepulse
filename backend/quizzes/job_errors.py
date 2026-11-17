"""Errors and professor-facing messages for background lecture jobs.

Every `error_message` shown to a professor is one of the strings below.
Tracebacks and raw error codes go to worker logs only.
"""

EMPTY_FILE = "This file is empty. Try re-uploading it."
UNREADABLE = "We couldn't read this file. Try re-uploading it."
NO_AUDIO = "This video has no audio."
TOO_SHORT = "Recording too short to make a quiz."
TOO_LONG = "Recording is longer than {hours:g} hours. Upload a shorter one."
NO_SPEECH = "No speech was detected."
INCOMPLETE = "The transcript looks incomplete. Try again."
NO_KEY = "Server isn't set up for transcription."
BAD_KEY = "The transcription key was rejected. Ask the site admin to check it."
NO_CREDITS = "Transcription credits ran out."
TOO_EXPENSIVE = "This recording is over the transcription cost limit."
SERVICE_BUSY = "Transcription service is busy. Try again later."
TIMEOUT = "Processing took too long."
INTERRUPTED = "Processing was interrupted, retry."
FILE_MISSING = "Recording file not found."
FILE_PERMISSION = "We couldn't open the recording file."
DISK_FULL = "The server ran out of space. Try again later."
QUEUE_FAILED = "Couldn't start processing, try again."
HANDOFF_FAILED = "Couldn't start question generation, retry."
UNEXPECTED = "Something went wrong. Try again."


class JobError(Exception):
    """A job failure. `message` is the text shown to the professor."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class PermanentError(JobError):
    """Retrying will not help."""


class TransientError(JobError):
    """A temporary problem. The job may be retried."""
