[app]

# (str) Title of your application
title = ADR Maintenance System

# (str) Package name
package.name = adrmaintenance

# (str) Package domain (needed for android/ios packaging)
package.domain = com.adr.maintenance

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (str) Application versioning (method 1)
version = 0.1

# (str) Application versioning (method 2)
# version.regex = __version__ = ['"](.*)['"]
# version.filename = %(source.dir)s/main.py

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,kivymd,requests,cython

# (str) Custom source folders for requirements
# requirements.source.kivy = ../../kivy

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (list) List of service to declare
#services = NAME:ENTRYPOINT_TO_PY,NAME2:ENTRYPOINT2_TO_PY

#
# OSX Specific
#

#
# author = © Copyright Info

# change the major version, or use the value 'None' to disable the version check
# osx.python_version = 3

# Kivy version to use
# osx.kivy_version = 1.9.1

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (string) Presplash animation using Lottie format.
# See https://lottie.github.io/lottie-specs/ for examples and https://airbnb.design/lottie/
# for general documentation.
# Lottie files can be created using various tools, like Adobe After Effect or Synfig.
#presplash.lottie = "path/to/lottie/file.json"

# (str) Adaptive icon of the application (used if Android API level is 26+ at runtime)
#icon.adaptive.icon = %(source.dir)s/data/icon-adaptive.png

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
# In past, was `android.arch` as we weren't supporting builds for multiple archs at the same time.
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) The format used to package the app for release mode (aab or apk).
# android.release_artifact = aab

# (str) The format used to package the app for debug mode (apk or aab).
# android.debug_artifact = apk

#
# Python for android (p4a) specific
#

# (str) The android entry point, default is ok if the source directory has an main.py file
#android.entrypoint = main.py:main

# (str) The name of the custom Android manifest to use
#android.manifest = custom_manifest.xml

# (str) Full name including package path
#android.apptheme = "@android:style/Theme.NoTitleBar"

# (list) Pattern to whitelist for the whole project
#android.whitelist =

# (str) Path to a custom whitelist file
#android.whitelist_src =

# (str) Path to a custom blacklist file
#android.blacklist_src =

# (list) List of Java .jar files to add to the libs so that pyjnius can access
# their classes. Don't add jars that you do not need, since extra jars can slow
# down the build process. Allows wildcards matching, for example:
# OUYA-ODK/libs/*.jar
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (list) List of Java files to add to the android project (can be java or a
# directory containing the files)
#android.add_src =

# (str) OUYA Console category. Should be one of GAME or APP
# If you leave this blank, OUYA support will not be enabled
#android.ouya.category = GAME

# (str) Filename of OUYA Console icon. It must be a 732x412 png image.
#android.ouya.icon.filename = %(source.dir)s/data/ouya_icon.png

# (str) XML file to include as an intent filters in <activity> tag
#android.manifest.intent_filters =

# (str) launchMode to set for the main activity
#android.manifest.launch_mode = standard

# (list) Android additional libraries to copy into libs/armeabi
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (list) Android additional libraries to copy into libs/armeabi-v7a
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (list) Android additional libraries to copy into libs/arm64-v8a
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (list) Android additional libraries to copy into libs/x86
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (list) Android additional libraries to copy into libs/x86_64
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (list) Android additional libraries to copy into libs/mips
#android.add_jivy_app/ars = foo.jar,bar.jar,path/to/more/*.jar

# (list) Android additional libraries to copy into libs/mips64
#android.add_jars = foo.jar,bar.jar,path/to/more/*.jar

# (bool) Android logcat messages via
#android.logcat = 

#
# iOS specific
#

# (str) Path to a custom kivy-ios folder
#ios.kivy_ios_dir = ../kivy-ios
# Alternately, specify the URL and branch of a git checkout:
ios.kivy_ios_dir = https://github.com/kivy/kivy-ios.git
ios.kivy_ios_branch = master

# Another platform dependency: ios-deploy
# Uncomment to use a custom checkout
#ios.ios_deploy_dir = ../ios_deploy
# Or specify a URL and branch
ios.ios_deploy_dir = https://github.com/phonegap/ios-deploy.git
ios.ios_deploy_branch = 1.7.0

# (bool) Whether or not to sign the code
ios.codesign.allowed = false

# (str) Name of the certificate to use for signing the debug version. Get a list of available identities: buildozer ios list_identities_signer
#ios.codesign.debug = "iPhone Developer: <lastname> <firstname> (<hexstring>)"

# (str) The development team to use for signing the debug version. Get a list of available teams: buildozer ios list_identities_signer
#ios.codesign.development_team.debug = <hexstring>

# (str) Name of the certificate to use for signing the release version.
#ios.codesign.release = %(ios.codesign.debug)s

# (str) The development team to use for signing the release version.
#ios.codesign.development_team.release = <hexstring>

# (str) URL pointing to .ipa file to be installed. This is only needed for the device build, not for the simulator build.
# It should point to a url that is accessible from the device.
#ios.manifest.app_url = <url>

# (str) URL pointing to an icon file. This is only needed for the device build, not for the simulator build.
# It should point to a url that is accessible from the device.
#ios.manifest.icon_url = <url>

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage, absolute or relative to spec file
# build_dir = ./.buildozer

# (str) Path to build output (i.e. .apk, .ipa) storage
# bin_dir = ./bin





















