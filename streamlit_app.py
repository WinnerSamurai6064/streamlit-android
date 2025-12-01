import streamlit as st
import subprocess
import os
import sys
import time
import shutil

# --- FORCE INSTALL PYNGROK ---
try:
    from pyngrok import ngrok
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])
    from pyngrok import ngrok

# --- CONFIGURATION ---
ISO_FILE = "android-x86-4.4-r5.iso"
ISO_URL = "https://sourceforge.net/projects/android-x86/files/Release%204.4/android-x86-4.4-r5.iso/download"
NOVNC_PORT = 6080

st.set_page_config(layout="wide", page_title="Android Debug Mode")
st.title("🔧 Android 4.4.4 (Safe Mode)")

def setup_environment():
    status = st.empty()
    
    # 1. CHECK ISO HEALTH
    if os.path.exists(ISO_FILE):
        size_mb = os.path.getsize(ISO_FILE) / (1024 * 1024)
        if size_mb < 300: # ISO should be ~443MB. If less than 300, it's broken.
            status.warning(f"⚠️ ISO corrupted ({size_mb:.1f}MB). Deleting and redownloading...")
            os.remove(ISO_FILE)
    
    # 2. DOWNLOAD IF MISSING
    if not os.path.exists(ISO_FILE):
        status.info("⬇️ Downloading Android ISO...")
        subprocess.run(["wget", "-q", "-O", ISO_FILE, ISO_URL], check=True)
    
    # 3. SETUP NOVNC
    if not os.path.exists("noVNC-1.4.0"):
        status.info("⬇️ Installing noVNC...")
        subprocess.run("wget -q -O novnc.zip https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.zip", shell=True)
        subprocess.run("unzip -q novnc.zip && rm novnc.zip", shell=True)
        if os.path.exists("noVNC-1.4.0/index.html"):
            os.remove("noVNC-1.4.0/index.html")
        subprocess.run("ln -s vnc.html noVNC-1.4.0/index.html", shell=True)
    
    status.empty()

def kill_existing_processes():
    subprocess.run("pkill -f qemu-system-i386", shell=True)
    subprocess.run("pkill -f websockify", shell=True)

def start_system():
    auth_token = st.secrets.get("NGROK_AUTH_TOKEN")
    if not auth_token:
        st.error("❌ Ngrok Token missing in Secrets!")
        st.stop()
    ngrok.set_auth_token(auth_token)

    # LOWERED RAM TO 256MB for Maximum Stability
    qemu_cmd = [
        "qemu-system-i386",
        "-m", "256",        # <--- LOWERED TO 256MB
        "-smp", "1",
        "-cpu", "qemu64",
        "-vga", "std",
        "-net", "nic,model=virtio", "-net", "user",
        "-cdrom", ISO_FILE,
        "-device", "usb-tablet",
        "-vnc", ":0",
        "-snapshot"
    ]
    
    # Launch QEMU
    qemu_proc = subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(4) 
    
    # DEBUG: CHECK FOR CRASH
    if qemu_proc.poll() is not None:
        stdout, stderr = qemu_proc.communicate()
        st.error("🚨 QEMU DIED! Here is the exact error:")
        st.code(stderr.decode()) # PRINT THE ERROR ON SCREEN
        st.stop()

    # Start Bridge
    websockify_cmd = [
        sys.executable, "-m", "websockify", 
        str(NOVNC_PORT), "localhost:5900", 
        "--web", "./noVNC-1.4.0"
    ]
    subprocess.Popen(websockify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    ngrok.kill()
    public_url = ngrok.connect(NOVNC_PORT, "http").public_url
    return public_url

# --- UI ---
setup_environment()

col1, col2 = st.columns([1, 3])

with col1:
    if st.button("▶️ Start Safe Mode"):
        with st.spinner("Booting (256MB RAM)..."):
            kill_existing_processes()
            url = start_system()
            st.session_state['android_url'] = url
            time.sleep(2)
            st.experimental_rerun()

    st.info("Running in Low RAM Mode (256MB). Performance will be slow but stable.")

with col2:
    if 'android_url' in st.session_state:
        final_url = f"{st.session_state['android_url']}/vnc.html?autoconnect=true"
        st.write(f"🔗 [Open Full Screen]({final_url})")
        st.components.v1.iframe(final_url, height=800)
    else:
        st.warning("Click Start.")
