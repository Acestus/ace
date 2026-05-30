(ns bb.common
  (:require [babashka.fs :as fs]
            [babashka.process :refer [process check]]
            [clojure.string :as str]
            [cheshire.core :as json]))

(defn fail [message]
  (binding [*out* *err*]
    (println message))
  (System/exit 1))

(defn script-dir [script-file]
  (str (fs/parent (fs/canonicalize script-file))))

(defn project-root [script-file]
  (str (fs/parent (script-dir script-file))))

(defn load-env! [script-file]
  (let [sdir (script-dir script-file)
        root (project-root script-file)
        paths [(str (fs/path root ".env"))
               (str (fs/path sdir ".env"))]]
    (doseq [p paths
            :when (fs/exists? p)
            line (str/split-lines (slurp p))
            :let [line (str/trim line)]
            :when (and (seq line)
                       (not (str/starts-with? line "#"))
                       (str/includes? line "="))]
      (let [[k v] (str/split line #"=" 2)]
        (System/setProperty (str/trim k) (str/trim v))))))

(defn env [k]
  (or (System/getenv k) (System/getProperty k)))

(defn require-env! [ks]
  (doseq [k ks]
    (when (str/blank? (env k))
      (fail (str "Missing required env var: " k)))))

(defn auth-header []
  (let [email (env "CONFLUENCE_EMAIL")
        token (env "WWEEKS_CONFLUENCE_API_TOKEN")
        raw (str email ":" token)]
    (str "Basic "
         (.encodeToString (java.util.Base64/getEncoder)
                          (.getBytes raw "UTF-8")))))

(defn confluence-base-url []
  "https://<YOUR_ATLASSIAN>.atlassian.net/wiki/rest/api")

(defn confluence-headers []
  {"Authorization" (auth-header)
   "Accept" "application/json"
   "Content-Type" "application/json"})

(defn run-cmd! [cmd]
  (-> (process cmd {:inherit true}) check))

(defn read-json [path]
  (json/parse-string (slurp path) true))

(defn write-json! [path data]
  (spit path (json/generate-string data {:pretty true})))
