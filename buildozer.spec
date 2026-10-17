[app]
title = Attack on the Aliens
package.name = attackaliens
package.domain = org.conturboll
source.dir = .
source.include_exts = py,png
version = 1.12.1
icon.filename = %(source.dir)s/icon.png
requirements = python3,pygame
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
