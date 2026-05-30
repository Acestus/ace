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
      (fail (str "Command failed (" (first cmd) "): " (str/trim (or err out "")))))))

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

(defn epoch-ms []
  (System/currentTimeMillis))

(defn api-post!
  "POST to SDP API, printing response body on error"
  [url access-token input-data]
  (let [{:keys [exit out err]} (sh "curl" "-sS" "-w" "\n%{http_code}" "-X" "POST"
                                   url
                                   "-H" "Accept: application/vnd.manageengine.sdp.v3+json"
                                   "-H" (str "Authorization: Zoho-oauthtoken " access-token)
                                   "-H" "Content-Type: application/x-www-form-urlencoded"
                                   "--data-urlencode" (str "input_data=" input-data))
        lines (str/split-lines (str/trim out))
        status (last lines)
        body (str/join "\n" (butlast lines))]
    (if (str/starts-with? status "2")
      body
      (fail (str "API returned HTTP " status ": " body)))))

(defn parse-time
  "Parse time string like '2h', '30m', '1h30m' into {:hours X :minutes Y}"
  [s]
  (let [hours   (or (some-> (re-find #"(\d+)h" s) second parse-long) 0)
        minutes (or (some-> (re-find #"(\d+)m" s) second parse-long) 0)]
    {:hours (str hours) :minutes (str minutes)}))

(defn get-access-token
  "Exchange refresh token for access token via Zoho OAuth"
  [client-id client-secret refresh-token]
  (let [response (run! "curl" "-fsS" "-X" "POST"
                       "https://accounts.zoho.com/oauth/v2/token"
                       "-d" (str "refresh_token=" refresh-token
                                 "&client_id=" client-id
                                 "&client_secret=" client-secret
                                 "&grant_type=refresh_token"))
        body (json/parse-string response true)]
    (or (:access_token body)
        (fail (str "OAuth token exchange failed: " response)))))

(defn issue-id-from-path [line]
  (second (re-find #"^\+\+\+ b/cases/(\d+)/" line)))

(defn resolve-sdp-id
  "Scan all markdown files in the case folder for SDP_ID: header.
   Returns the first SDP_ID found, or the folder name as fallback."
  [folder-id]
  (let [dir   (str "cases/" folder-id)
        files (filter #(str/ends-with? (str %) ".md") (fs/list-dir dir))]
    (or (some (fn [md-file]
                (second (re-find #"(?m)^SDP_ID:\s*(\S+)" (slurp (str md-file)))))
              files)
        folder-id)))

(defn parse-worklog [line]
  (when-let [[_ spent text] (re-matches #"^\+\s*[-*]\s*WORKLOG\s+([^:]+):\s*(.+)\s*$" line)]
    {:type :worklog
     :timeSpent (str/trim spent)
     :text (str/trim text)}))

(defn parse-comment [line]
  (when-let [[_ text] (re-matches #"^\+\s*[-*]\s*COMMENT:\s*(.+)\s*$" line)]
    {:type :comment
     :text (str/trim text)}))

(defn parse-nudge [line]
  (when-let [[_ text] (re-matches #"^\+\s*[-*]\s*NUDGE:\s*(.+)\s*$" line)]
    {:type :nudge
     :text (str/trim text)}))

;; --- Main ---

(let [args (vec *command-line-args*)
      arg-map (->> (partition 2 args)
                   (map (fn [[k v]] [(keyword (str/replace k #"^--" "")) v]))
                   (into {}))
      from-sha (:from arg-map)
      to-sha   (:to arg-map)
      script-dir (str (fs/parent (fs/canonicalize *file*)))
      root       (str (fs/parent script-dir))
      sdp-base   "https://<YOUR_SDP>.sdpondemand.manageengine.com/app/698819937"
      _          (load-env! (str (fs/path root ".env")))
      _          (load-env! (str (fs/path script-dir ".env")))
      sdp-creds  (env "WWEEKS_SDP")]

  (when (or (str/blank? from-sha) (str/blank? to-sha))
    (fail "Usage: bb scripts/sync-sdp-worklog.bb --from <sha> --to <sha>"))

  (when (str/blank? sdp-creds)
    (fail "Missing WWEEKS_SDP in environment/.env (JSON with client_id, client_secret, refresh_token)"))

  (let [creds         (json/parse-string sdp-creds true)
        client-id     (:client_id creds)
        client-secret (:client_secret creds)
        refresh-token (:refresh_token creds)
        _             (when (or (str/blank? client-id) (str/blank? client-secret) (str/blank? refresh-token))
                        (fail "WWEEKS_SDP JSON must contain client_id, client_secret, refresh_token"))
        access-token  (get-access-token client-id client-secret refresh-token)
        diff          (run! "git" "--no-pager" "diff" "--unified=0" "--no-color" from-sha to-sha "--" "cases/")
        lines         (str/split-lines diff)
        entries       (atom [])
        current-id    (atom nil)]

    (println "✓ OAuth token acquired")

    (doseq [line lines]
      (when-let [id (issue-id-from-path line)]
        (reset! current-id id))
      (when (and @current-id
                 (str/starts-with? line "+")
                 (not (str/starts-with? line "+++")))
        (when-let [w (parse-worklog line)]
          (swap! entries conj (assoc w :id @current-id)))
        (when-let [c (parse-comment line)]
          (swap! entries conj (assoc c :id @current-id)))
        (when-let [n (parse-nudge line)]
          (swap! entries conj (assoc n :id @current-id)))))

    (let [deduped (vals (into {} (map (fn [e] [[(:id e) (:type e) (:timeSpent e) (:text e)] e]) @entries)))]
      (if (empty? deduped)
        (println "No new WORKLOG/COMMENT/NUDGE lines detected in cases/ changes.")
        (do
          (println (str "Found " (count deduped) " new SDP sync entries."))
          (doseq [{:keys [id type timeSpent text]} deduped]
            (let [sdp-id (resolve-sdp-id id)]
              (when (= sdp-id id)
                (binding [*out* *err*]
                  (println (str "  ⚠ No SDP_ID: header found in cases/" id "/ — falling back to folder name. Add 'SDP_ID: <internal-id>' to the markdown file."))))
              (println (str "  Ticket " id " → SDP request " sdp-id))
              (case type
              :worklog
              (let [{:keys [hours minutes]} (parse-time timeSpent)
                    now-ms (epoch-ms)
                    payload {:worklog {:description text
                                       :start_time {:value now-ms}
                                       :time_spent {:hours hours :minutes minutes}
                                       :owner {:email_id "<YOUR_EMAIL>"}
                                       :include_nonoperational_hours true
                                       :mark_first_response false}}
                    input-data (json/generate-string payload)]
                (api-post! (str sdp-base "/api/v3/requests/" sdp-id "/worklogs")
                           access-token input-data)
                (println (str "  ✓ Worklog added to SDP-" id " (" timeSpent "): " text)))

              :comment
              (let [payload {:request_note {:description text
                                            :show_to_requester false
                                            :mark_first_response false
                                            :add_to_linked_requests false}}
                    input-data (json/generate-string payload)]
                (api-post! (str sdp-base "/api/v3/requests/" sdp-id "/notes")
                           access-token input-data)
                (println (str "  ✓ Internal note added to SDP-" id ": " text)))

              :nudge
              (let [payload {:request_note {:description text
                                            :show_to_requester true
                                            :mark_first_response false
                                            :add_to_linked_requests false}}
                    input-data (json/generate-string payload)]
                (api-post! (str sdp-base "/api/v3/requests/" sdp-id "/notes")
                           access-token input-data)
                (println (str "  ✓ Public nudge added to SDP-" id " (visible to requester): " text)))

              nil))))))))
