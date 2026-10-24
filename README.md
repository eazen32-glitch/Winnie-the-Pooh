# Winnie-the-Pooh

A browser-based career workspace prototype for exploring skills, career opportunities, workforce trends, and interview schedules.

Repository: https://github.com/eazen32-glitch/Winnie-the-Pooh

## Run the prototype

1. Download or clone this repository.
2. Open `mainpage.html` in a current browser with JavaScript enabled.
3. Keep an internet connection available: styles, icons, fonts, and charts load from external CDNs.

For a local HTTP preview, if Python 3 is installed, run this command from the repository folder:

```sh
python -m http.server 8000 --bind 127.0.0.1
```

Then visit http://127.0.0.1:8000/mainpage.html. On Windows, `py` can be used instead of `python` if that is how Python is installed.

The checked-in frontend has no package-install or build step. This preview command serves static files; it does not provide a backend or execute Python application files.

## Included pages

| File | Purpose |
| --- | --- |
| `mainpage.html` | Main career workspace, guest/job-seeker/HR views, and skills-and-roles radar |
| `analytics_trends.html` | Interactive charts using illustrative workforce data |
| `calendar-button.html` | Calendar interface with sample events; also embedded in the home page |
| `interviews.html` | Upcoming-interview interface with sample sessions shown in Malaysia time |

Image files provide logos and screenshots used by or stored alongside the prototype.

## Demo status and limitations

- This repository contains a frontend prototype. A complete backend, authenticated account system, and production booking workflow are not included.
- CV-related links point to `app.py`, which is not present. Those links cannot run the CV feature from this checkout. A Python application also needs its own runtime and server integration.
- Some AI, job-management, and navigation controls are placeholders or depend on integration code that is not included. Their labels should not be treated as proof of a working AI service.
- The analytics dashboard uses sample values, not verified live workforce statistics.
- The skills radar uses an embedded snapshot dated 24 October 2026. Its source metadata identifies the Simplify / Coder Quad new-graduate listings and Hugging Face Transformers releases. It describes a limited international sample, not Malaysian labour-market statistics. No live radar API is configured in the checked-in page.
- Calendar events and interview sessions are examples. Sample interview buttons without a meeting URL do not connect to a real meeting.
- External CDN resources require internet access. Some CDN URLs are unpinned, so upstream changes may affect the preview.

## Suggested review path

1. Open `mainpage.html` and inspect the home page and available role views.
2. Search or filter the skills-and-roles radar and inspect its dated evidence links.
3. Open `analytics_trends.html` and switch between domain filters.
4. Open the calendar and inspect its sample events.
5. Open `interviews.html` to inspect the sample interview schedule.

## License and attribution

Copyright 2026 Winnie-the-Pooh contributors.

The project's original source code and documentation are licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

Third-party libraries, fonts, datasets, images, trademarks, and other third-party materials retain their own terms and are not relicensed by the project's Apache license. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for identified resources and unresolved provenance checks.
