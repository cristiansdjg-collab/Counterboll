[app]
title = Attack on the Aliens
package.name = attackaliens
package.domain = org.conturboll
source.dir = .
source.include_exts = py,png
version = 1.12.6
icon.filename = %(source.dir)s/icon.png
presplash.filename = %(source.dir)s/presplash.png
presplash.color = #070616
requirements = hostpython3==3.10.12,python3==3.10.12,pygame
orientation = landscape
fullscreen = 1
android.api = 33
android.minapi = 21
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
