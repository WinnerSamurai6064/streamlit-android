import streamlit as st
import subprocess
import os
import sys
import time

# --- 1. DEPENDENCY CHECK ---
try:
    from pyngrok import ngrok
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok"])
    from pyngrok import ngrok

# --- CONFIGURATION ---
ISO_FILE = "android-x86-4.4-r5.iso"
# Using OSDN mirror which is often more reliable for direct wget than SourceForge
ISO_URL = "https://sourceforge.net/projects/android-x86/files/Release%204.4/android-x86-4.4-r5.iso/download"
NOVNC_PORT = 6080

st.set_page_config(layout="wide", page_title="Android KitKat")
st.title("📱 Android 4.4.4 (Self-Healing Mode)")

# --- 2. SETUP FUNCTIONS ---
def setup_environment():
    status = st.empty()
    
    # --- CORRUPTION FIX: Check File Size ---
    if os.path.exists(ISO_FILE):
        # Get file size in MB
        size_mb = os.path.getsize(ISO_FILE) / (1024 * 1024)
        if size_mb < 400: # The real ISO is ~443MB. If <400, it's broken.
            status.error(f"⚠️ ISO Corrupted ({size_mb:.1f}MB). Deleting to redownload...")
            time.sleep(2)
            os.remove(ISO_FILE)
            
    # Download Android ISO if missing
    if not os.path.exists(ISO_FILE):
        status.info("⬇️ Downloading Android ISO (This takes ~45s)...")
        # Added --tries=3 to retry if connection drops
        subprocess.run(["wget", "--tries=3", "-q", "-O", ISO_FILE, ISO_URL], check=True)
    
    # Download noVNC
    if not os.path.exists("noVNC-1.4.0"):
        status.info("⬇️ Installing Web Interface...")
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
    # Authenticate Ngrok
    if "NGROK_AUTH_TOKEN" not in st.secrets:
        st.error("❌ NGROK_AUTH_TOKEN missing in Secrets!")
        st.stop()
    
    auth_token = st.secrets["NGROK_AUTH_TOKEN"]
    ngrok.set_auth_token(auth_token)

    # Start QEMU (Android Emulator)
    # -usb: Fixes 'No usb-bus' error
    # -cpu qemu32: Fixes TCG warnings
    qemu_cmd = [
        "qemu-system-i386",
        "-m", "256",
        "-smp", "1",
        "-cpu", "qemu32",
        "-machine", "pc",
        "-usb",
        "-vga", "std",
        "-net", "nic,model=virtio", "-net", "user",
        "-cdrom", ISO_FILE,
        "-device", "usb-tablet",
        "-vnc", ":0",
        "-snapshot"
    ]
    
    qemu_proc = subprocess.Popen(qemu_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(5) # Give it time to initialize
    
    # Check for immediate crash
    if qemu_proc.poll() is not None:
        stdout, stderr = qemu_proc.communicate()
        st.error("🚨 QEMU Crashed! Error logs:")
        st.code(stderr.decode())
        st.stop()

    # Start Bridge
    websockify_cmd = [
        sys.executable, "-m", "websockify", 
        str(NOVNC_PORT), "localhost:5900", 
        "--web", "./noVNC-1.4.0"
    ]
    subprocess.Popen(websockify_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Create Tunnel
    ngrok.kill()
    public_url = ngrok.connect(NOVNC_PORT, "http").public_url
    return public_url

# --- 3. MAIN UI ---
setup_environment()

col1, col2 = st.columns([1, 3])

with col1:
    st.write("### 🎮 Controls")
    if st.button("▶️ Start / Restart", type="primary"):
        with st.spinner("Repairing & Booting..."):
            kill_existing_processes()
            try:
                url = start_system()
                st.session_state['android_url'] = url
                st.success("System Online!")
                time.sleep(1)
                st.rerun() # <--- FIXED: Replaced experimental_rerun
            except Exception as e:
                st.error(f"Error: {e}")

    st.markdown("---")
    st.info("""
    **If Boot Fails:**
    The system will auto-delete bad files on the next click. 
    Just click 'Start' again.
    
    **Instructions:**
    1. Wait for Black Screen.
    2. Tap **'Live CD - VESA'**.
    3. Choose **800x600**.
    """)

with col2:
    if 'android_url' in st.session_state:
        final_url = f"{st.session_state['android_url']}/vnc.html?autoconnect=true"
        st.write(f"🔗 [Full Screen Link]({final_url})")
        st.components.v1.iframe(final_url, height=850)
    else:
        st.warning("Click 'Start / Restart' to boot.")
