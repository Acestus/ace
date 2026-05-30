#!/usr/bin/env bb

(require '[babashka.fs :as fs]
         '[babashka.process :refer [sh]]
         '[cheshire.core :as json]
         '[clojure.string :as str])

(defn fail [message]
  (binding [*out* *err*]
    (println message))
  (System/exit 1))

(defn run! [& cmd]
  (let [{:keys [exit out err]} (apply sh cmd)]
    (when (seq err)
      (binding [*out* *err*] (print err)))
    (if (zero? exit)
      out
      (fail (str "Command failed: " (first cmd))))))

(defn load-env! [path]
  (when (fs/exists? path)
    (doseq [line (str/split-lines (slurp path))]
      (when-let [[_ k v] (re-matches #"^\s*([^=#\s]+)\s*=\s*(.*?)\s*$" line)]
        (System/setProperty k v)))))

(defn env [k]
  (or (System/getenv k) (System/getProperty k)))

(defn sanitize-filename [s]
  (-> s
      (str/replace #"[<>:\"/\\|?*\u0000-\u001F]" "-")
      (str/replace #"\s+" " ")
      (str/trim)))

(defn now-str []
  (.format (java.time.format.DateTimeFormatter/ofPattern "yyyy-MM-dd HH:mm")
           (java.time.LocalDateTime/now)))

(defn ensure-file [path]
  (when-not (fs/exists? path)
    (fs/create-dirs (fs/parent path))
    (spit path "")))

(let [script-dir (str (fs/parent (fs/canonicalize *file*)))
      root       (str (fs/parent script-dir))
      issues-path (str (fs/path root "issues"))
      tasks-path (str (fs/path root "planner/tasks-list.txt"))
      jira-url   "https://<YOUR_ATLASSIAN>.atlassian.net"
      jql        "assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC"
      _          (load-env! (str (fs/path root ".env")))
      _          (load-env! (str (fs/path script-dir ".env")))
      email      (env "CONFLUENCE_EMAIL")
      token      (env "WWEEKS_CONFLUENCE_API_TOKEN")]

  (when (or (str/blank? email) (str/blank? token))
    (fail "Missing CONFLUENCE_EMAIL or WWEEKS_CONFLUENCE_API_TOKEN in .env"))

  (fs/create-dirs issues-path)
  (ensure-file tasks-path)

  (let [search-url (str jira-url "/rest/api/3/search/jql")
        auth       (str email ":" token)
        payload    (run! "curl" "-fsS"
                         "-G"
                         "-H" (str "Authorization: Basic "
                                   (.encodeToString (java.util.Base64/getEncoder)
                                                    (.getBytes auth "UTF-8")))
                         "-H" "Accept: application/json"
                         "--data-urlencode" (str "jql=" jql)
                         "--data-urlencode" "maxResults=100"
                         "--data-urlencode" "fields=summary,status"
                         search-url)
        issues     (get (json/parse-string payload true) :issues)
        existing   (if (fs/exists? tasks-path)
                     (str/split-lines (slurp tasks-path))
                     [])
        existing-set (set existing)
        timestamp  (now-str)
        counters   (atom {:issues-created 0 :issues-existing 0 :tasks-added 0})
        new-lines  (atom [])]

    (doseq [issue issues]
      (let [k          (:key issue)
            summary    (get-in issue [:fields :summary] "")
            status     (get-in issue [:fields :status :name] "")
            safe       (sanitize-filename summary)
            case-dir   (str (fs/path issues-path k))
            case-file  (str (fs/path case-dir (str k " - " safe ".md")))
            task-line  (str "- [ ] " k " - " summary)]
        (fs/create-dirs case-dir)
        (if (fs/exists? case-file)
          (swap! counters update :issues-existing inc)
          (do
            (spit case-file
                  (str "# " k " - " summary "\n"
                       "<!-- jira: " k " -->\n"
                       "<!-- last_synced: 1970-01-01T00:00:00Z -->\n\n"
                       "## Description\n\n"
                       "------------------------------------------------\n\n"
                       "- Jira: " jira-url "/browse/" k "\n"
                       "- Status: " status "\n\n"
                       "## Actions\n\n"
                       "------------------------------------------------\n\n"
                       "### " timestamp "\n\n"
                       "- WORKLOG 15m:\n"
                       "- COMMENT:\n\n"
                       "## Follow-up\n\n"
                       "------------------------------------------------\n"
                       "Status:\n"
                       "TODO:\n"))
            (swap! counters update :issues-created inc)))
        (when-not (contains? existing-set task-line)
          (swap! new-lines conj task-line)
          (swap! counters update :tasks-added inc))))

    (when (seq @new-lines)
      (spit tasks-path
            (str (str/join "\n" (concat @new-lines existing))
                 (when (seq (concat @new-lines existing)) "\n"))))

    (println (str "Issues returned: " (count issues)))
    (println (str "Issue files created: " (:issues-created @counters)))
    (println (str "Issue files already present: " (:issues-existing @counters)))
    (println (str "Tasks added: " (:tasks-added @counters)))))
