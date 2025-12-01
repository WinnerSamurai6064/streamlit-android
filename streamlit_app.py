def start_system():
    auth_token = st.secrets.get("NGROK_AUTH_TOKEN")
    if not auth_token:
        st.error("❌ Ngrok Token missing in Secrets!")
        st.stop()
    ngrok.set_auth_token(auth_token)

    # LOWERED RAM TO 256MB for Maximum Stability
    qemu_cmd = [
        "qemu-system-i386",
        "-m", "256",
        "-smp", "1",
        "-cpu", "qemu32",    # CHANGED: 'qemu32' stops the TCG warnings
        "-machine", "pc",    # CHANGED: Ensures standard PC motherboard
        "-usb",              # CRITICAL FIX: Adds the USB Controller
        "-vga", "std",
        "-net", "nic,model=virtio", "-net", "user",
        "-cdrom", ISO_FILE,
        "-device", "usb-tablet", # Now this has a bus to plug into!
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
        st.code(stderr.decode()) 
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
