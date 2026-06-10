# CronPilot 发行版检测（source 用，勿直接执行）

cronpilot_os_id() {
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${ID:-unknown}"
    return 0
  fi
  echo "unknown"
}

cronpilot_os_version() {
  if [ -f /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    echo "${VERSION_ID:-}"
    return 0
  fi
  echo ""
}

cronpilot_is_ubuntu() {
  case "$(cronpilot_os_id)" in
    ubuntu|debian) return 0 ;;
  esac
  return 1
}

cronpilot_is_rhel_family() {
  case "$(cronpilot_os_id)" in
    ubuntu|debian) return 1 ;;
    centos|rhel|rocky|almalinux|ol|scientific) return 0 ;;
  esac
  [ -f /etc/redhat-release ]
}

cronpilot_is_centos7() {
  cronpilot_is_rhel_family || return 1
  [ "$(cronpilot_os_version | cut -d. -f1)" = "7" ]
}

cronpilot_is_centos8() {
  cronpilot_is_rhel_family || return 1
  [ "$(cronpilot_os_version | cut -d. -f1)" = "8" ]
}
