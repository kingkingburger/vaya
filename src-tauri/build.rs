fn main() {
    ensure_debug_sidecar_placeholder();
    tauri_build::build()
}

fn ensure_debug_sidecar_placeholder() {
    if std::env::var("PROFILE").as_deref() != Ok("debug") {
        return;
    }

    let Ok(target) = std::env::var("TARGET") else {
        return;
    };

    let extension = if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("windows") {
        ".exe"
    } else {
        ""
    };
    let path = std::path::Path::new("binaries").join(format!("vaya-backend-{target}{extension}"));

    if path.exists() {
        return;
    }

    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let _ = std::fs::write(
        path,
        b"debug placeholder; run `bun run build:backend-sidecar` for production builds\n",
    );
}
