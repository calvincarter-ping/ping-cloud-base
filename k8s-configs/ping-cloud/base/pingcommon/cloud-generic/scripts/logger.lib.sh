#!/usr/bin/env sh

# Set default verbose level for deploy logs
VERBOSITY=${VERBOSITY:-3}

ERR_LVL=1
WRN_LVL=2
INF_LVL=3
DBG_LVL=4

########################################################################################################################
# Logs the provided message at the provided log level. Default log level is INFO, if not provided.
#
# Arguments
#   $1 -> The log message.
#   $2 -> Optional log level. Default is INFO.
########################################################################################################################
beluga_log() {
  VERBOSITY=$(echo "${VERBOSITY}" | tr '[:upper:]' '[:lower:]')
  case ${VERBOSITY} in
    [1-4]) ;;
    debug) VERBOSITY=4 ;;
    info) VERBOSITY=3 ;;
    warn) VERBOSITY=2 ;;
    error) VERBOSITY=1 ;;
    *) echo "Use number (1-4) or string (debug, info, warn, error) in VERBOSITY variable. Value: '${VERBOSITY}'" ; exit 1 ;;
  esac

  file_name="$(basename "$0")"
  message="$1"
  log_level="${2:-INFO}"
  case ${log_level} in
  DEBUG)
    verb_lvl=${DBG_LVL}
    ;;
  WARN)
    verb_lvl=${WRN_LVL}
    ;;
  ERROR)
    verb_lvl=${ERR_LVL}
    ;;
  *)
    verb_lvl=${INF_LVL}
    ;;
  esac
  format='+%Y-%m-%d %H:%M:%S'
  timestamp="$(TZ=UTC date "${format}")"
  if [ "${VERBOSITY}" -ge "${verb_lvl}" ]; then
    echo "${file_name}: ${timestamp} ${log_level} ${message}"
  fi
}

########################################################################################################################
# Logs the provided message and set the log level to ERROR.
#
# Arguments
#   $1 -> The log message.
########################################################################################################################
beluga_error() {
  beluga_log "$1" 'ERROR'
}

########################################################################################################################
# Logs the provided message and set the log level to WARN.
#
# Arguments
#   $1 -> The log message.
########################################################################################################################
beluga_warn() {
  beluga_log "$1" 'WARN'
}

########################################################################################################################
# Logs the provided message and set the log level to DEBUG.
#
# Arguments
#   $1 -> The log message.
########################################################################################################################
beluga_debug() {
  beluga_log "$1" 'DEBUG'
}

########################################################################################################################
# Write Logs to file.
#
# Arguments
#   $1 -> The log message.
#   $2 -> file name(example: liveness or readiness) 
########################################################################################################################

beluga_log_file() {
  local message="$1"
  local filename="$2"

  local log_file="/tmp/${log_file_name}.log"
  local log_output=$(beluga_log "$message")
  local max_lines=1000

  echo "$log_output"
  echo "$log_output" >"$log_file"

  #limit to 1000 lines by creating  a tmp log file and replacing that
  if [ $(wc -l < "$log_file") -gt $max_lines ]; then
    tail -1000 $log_file > tmp.log && cp tmp.log $log_file && rm tmp.log    
  fi
}

########################################################################################################################
# Write Logs to file.
#
# Arguments
#   $1 -> The log message.
#   $2 -> file name(example: liveness or readiness) 
########################################################################################################################
beluga_error_file() {
  local message="$1"
  local filename="$2"

  local log_file="/tmp/${filename}.log"
  local log_output=$(beluga_error "$message")
  local max_lines=1000

  echo "$log_output"
  echo "$log_output" >"$log_file"

  #limit to 1000 lines by creating  a tmp log file and replacing that
  if [ $(wc -l < "$log_file") -gt $max_lines ]; then
    tail -1000 $log_file > tmp.log && cp tmp.log $log_file && rm tmp.log
  fi  
}
