import streamlit as st
import subprocess
import os
import sys
import time
import shutil

# --- FORCE INSTALL PYNGROK (Fallback) ---
try:
    from pyngrok import ngrok
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])
    from pyngrok import ngrok

# --- CONFIGURATION ---
ISO_FILE = "android-x86-4.4-r5.iso"
ISO_URL = "https://sourceforge.net/projects/android-x86/files/Release%204.4/android-x86-4.4-r5.iso/download"
NOVNC_PORT = 6080
VNC_PORT = 5900

st.set_page_config(layout="wide", page_title="Android Cloud")
st.title("📱 Android 4.4.4 (KitKat)")

# --- 1. SETUP FUNCTIONS ---
def setup_environment():
    status = st.empty()
    if not os.path.exists(ISO_FILE):
        status.info("⬇️ Downloading Android ISO (Wait ~30s)...")
        subprocess.run(["wget", "-q", "-O", ISO_FILE, ISO_URL], check=True)
    
    if not os.path.exists("noVNC-1.4.0"):
        status.info("⬇️ Installing noVNC...")
        subprocess.run("wget -q -O novnc.zip https://github.com/novnc/noVNC/archive/refs/tags/v1.4.0.zip", shell=True)
        subprocess.run("unzip -q novnc.zip && rm novnc.zip", shell=True)
        # Link the special vnc.html to index.html so it loads by default
        if os.path.exists("noVNC-1.4.0/index.html"):
            os.remove("noVNC-1.4.0/index.html")
        subprocess.run("ln -s vnc.html noVNC-1.4.0/index.html", shell=True)
    
    status.empty()

def kill_existing_processes():
    # Cleanup to prevent port conflicts
    subprocess.run("pkill -f qemu-system-i386", shell=True)
    subprocess.run("pkill -f websockify", shell=True)

def start_system():
    # A. Verify Ngrok
    auth_token = st.secrets.get("NGROK_AUTH_TOKEN")
    if not auth_token:
        st.error("❌ Ngrok Token missing in Secrets!")
        st.stop()
    ngrok.set_auth_token(auth_token)

    # B. Start QEMU (Android)
    # Reduced RAM to 512MB to prevent Cloud Crash
    qemu_cmd = [
        "qemu-system-i386",
        "-m", "512",        # LOWERED RAM for stability
        "-smp", "1",
        "-cpu", "qemu64",
        "-vga", "std",
        "-net", "nic,model=virtio", "-net", "user",
        "-cdrom", ISO_FILE,
        "-device", "usb-tablet",
        "-vnc", ":0",       # Listens on localhost:5900
        "-snapshot"
    ]
    
    # We use Popen so it runs in background
    qemu_proc = subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(3) # Give QEMU a moment to breathe
    
    # Check if QEMU died immediately
    if qemu_proc.poll() is not None:
        st.error("🚨 QEMU Crashed! View logs in 'Manage App' -> 'Logs'.")
        st.stop()

    # C. Start Websockify (The Bridge) directly via Python
    # This avoids the permission errors of the shell script
    websockify_cmd = [
        sys.executable, "-m", "websockify", 
        str(NOVNC_PORT), "localhost:5900", 
        "--web", "./noVNC-1.4.0"
    ]
    subprocess.Popen(websockify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # D. Start Tunnel
    # Kill old tunnels
    ngrok.kill()
    public_url = ngrok.connect(NOVNC_PORT, "http").public_url
    return public_url

# --- 2. MAIN UI ---
setup_environment()

col1, col2 = st.columns([1, 3])

with col1:
    if st.button("▶️ Start / Restart"):
        with st.spinner("Booting..."):
            kill_existing_processes()
            url = start_system()
            st.session_state['android_url'] = url
            time.sleep(2) # Wait for connections to stabilize
            st.experimental_rerun()

    st.markdown("---")
    st.info("**Tips:**\n1. Select 'Live CD - VESA'\n2. Use **800x600** resolution.\n3. Open Left Menu ⚙️ -> Scaling -> **Remote Resizing**.")

with col2:
    if 'android_url' in st.session_state:
        final_url = f"{st.session_state['android_url']}/vnc.html?autoconnect=true"
        # We display the link just in case the iframe blocks it
        st.write(f"🔗 [Open Full Screen]({final_url})")
        st.components.v1.iframe(final_url, height=800)
    else:
        st.warning("Click Start to boot the phone.")

