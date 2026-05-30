#!/usr/bin/env bb

(require '[babashka.process :refer [sh]]
         '[babashka.fs :as fs]
         '[clojure.string :as str]
         '[cheshire.core :as json])

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
    (doseq [line (str/split-lines (slurp path))
            :let [line (str/trim line)]
            :when (and (seq line)
                       (not (str/starts-with? line "#"))
                       (str/includes? line "="))]
      (let [[k v] (str/split line #"=" 2)]
        (System/setProperty (str/trim k) (str/trim v))))))

(defn env [k]
  (or (System/getenv k) (System/getProperty k)))

(defn iso-now []
  (.format (java.time.format.DateTimeFormatter/ofPattern "yyyy-MM-dd'T'HH:mm:ss.SSSZ")
           (java.time.ZonedDateTime/now)))

(defn issue-key-from-path [line]
  (second (re-find #"^\+\+\+ b/issues/([A-Z]+-\d+)" line)))

(defn parse-worklog [line]
  (when-let [[_ spent text] (re-matches #"^\+\s*[-*]\s*WORKLOG\s+([^:]+):\s*(.+)\s*$" line)]
    {:type :worklog
     :timeSpent (str/trim spent)
     :text (str/trim text)}))

(defn parse-comment [line]
  (when-let [[_ text] (re-matches #"^\+\s*[-*]\s*COMMENT:\s*(.+)\s*$" line)]
    {:type :comment
     :text (str/trim text)}))

(defn adf-paragraph [text]
  {:type "doc"
   :version 1
   :content [{:type "paragraph"
              :content [{:type "text" :text text}]}]})

(let [args (vec *command-line-args*)
      arg-map (->> (partition 2 args)
                   (map (fn [[k v]] [(keyword (str/replace k #"^--" "")) v]))
                   (into {}))
      from-sha (:from arg-map)
      to-sha   (:to arg-map)
      script-dir (str (fs/parent (fs/canonicalize *file*)))
      root       (str (fs/parent script-dir))
      jira-url   "https://<YOUR_ATLASSIAN>.atlassian.net"
      _          (load-env! (str (fs/path root ".env")))
      _          (load-env! (str (fs/path script-dir ".env")))
      email      (env "CONFLUENCE_EMAIL")
      token      (env "WWEEKS_CONFLUENCE_API_TOKEN")]

  (when (or (str/blank? from-sha) (str/blank? to-sha))
    (fail "Usage: bb scripts/sync-jira-worklog.bb --from <sha> --to <sha>"))

  (when (or (str/blank? email) (str/blank? token))
    (fail "Missing CONFLUENCE_EMAIL or WWEEKS_CONFLUENCE_API_TOKEN in environment/.env"))

  (let [diff (run! "git" "--no-pager" "diff" "--unified=0" "--no-color" from-sha to-sha "--" "issues/")
        lines (str/split-lines diff)
        auth  (.encodeToString (java.util.Base64/getEncoder)
                               (.getBytes (str email ":" token) "UTF-8"))
        entries (atom [])
        current-issue (atom nil)]

    (doseq [line lines]
      (when-let [k (issue-key-from-path line)]
        (reset! current-issue k))
      (when (and @current-issue
                 (str/starts-with? line "+")
                 (not (str/starts-with? line "+++")))
        (when-let [w (parse-worklog line)]
          (swap! entries conj (assoc w :issue @current-issue)))
        (when-let [c (parse-comment line)]
          (swap! entries conj (assoc c :issue @current-issue)))))

    (let [deduped (vals (into {} (map (fn [e] [[(:issue e) (:type e) (:timeSpent e) (:text e)] e]) @entries)))]
      (if (empty? deduped)
        (println "No new WORKLOG/COMMENT lines detected in issues/ changes.")
        (do
          (println (str "Found " (count deduped) " new Jira sync entries."))
          (doseq [{:keys [issue type timeSpent text]} deduped]
            (case type
              :worklog
              (let [payload {:timeSpent timeSpent
                             :started (iso-now)
                             :comment (adf-paragraph text)}]
                (run! "curl" "-fsS" "-X" "POST"
                      "-H" (str "Authorization: Basic " auth)
                      "-H" "Accept: application/json"
                      "-H" "Content-Type: application/json"
                      "--data" (json/generate-string payload)
                      (str jira-url "/rest/api/3/issue/" issue "/worklog"))
                (println (str "Worklog added to " issue " (" timeSpent ")")))

              :comment
              (let [payload {:body (adf-paragraph text)}]
                (run! "curl" "-fsS" "-X" "POST"
                      "-H" (str "Authorization: Basic " auth)
                      "-H" "Accept: application/json"
                      "-H" "Content-Type: application/json"
                      "--data" (json/generate-string payload)
                      (str jira-url "/rest/api/3/issue/" issue "/comment"))
                (println (str "Comment added to " issue)))

              nil)))))))
