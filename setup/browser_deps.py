#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import time

from setup import Command, is_ci


class BrowserDeps(Command):
    description = 'Download the binary dependencies needed for browser automation'
    usage_help = (
        'The Camoufox browser and the browserforge fingerprint data files are normally downloaded on demand,'
        ' the first time browser automation is used. This command downloads them ahead of time, which is what'
        ' CI does so that the browser automation tests are not skipped.'
    )

    def add_options(self, parser):
        parser.add_option('--allow-prerelease', default=False, action='store_true', help='Use pre-release builds of the Camoufox browser')
        parser.add_option('--num-attempts', type=int, default=5 if is_ci else 1, help='Number of times to retry the download before giving up')

    def download(self, installer, func, *a, **kw):
        # Downloading hundreds of megabytes from GitHub is flaky often enough to be worth retrying
        for attempt in range(self.num_attempts):
            try:
                return func(*a, **kw)
            except Exception as err:
                # A failed install is wrapped in InstallFailed, so look at the
                # original error too. A 403 means a rate limit or an
                # authorization failure, neither of which will resolve itself
                # in the few seconds we would wait
                if 403 in (getattr(err, 'code', -1), getattr(err.__cause__, 'code', -1)):
                    raise
                if attempt >= self.num_attempts - 1:
                    raise
                self.info(f'Download failed with error: {err}, retrying...')
                time.sleep(2 * (attempt + 1))
                # The failure is recorded so that installing is not tried again
                # for a while, which would make every retry fail immediately
                installer.forget_install_failure()

    def run(self, opts):
        # Not the live version of download_deps, see live_module(), as this
        # runs from the source tree, whose download_deps is what should be used
        from calibre.web.automate.download_deps import browserforge_data, camoufox_binary, camoufox_installer

        self.num_attempts = max(1, opts.num_attempts)
        self.info('Camoufox browser:', self.download(camoufox_installer, camoufox_binary, allow_prerelease=opts.allow_prerelease))
        # browserforge_data() falls back to the data files bundled with apify_fingerprint_datapoints, so retrying it is pointless
        self.info('browserforge data:', browserforge_data(patch_browserforge=False))
