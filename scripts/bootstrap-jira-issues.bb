#!/usr/bin/env bb

(load-file (str (babashka.fs/path (babashka.fs/parent *file*) "bootstrap-jira-cases.bb")))
