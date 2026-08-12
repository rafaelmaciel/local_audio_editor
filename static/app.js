let currentTrack = null;
let wave = null;

const $ = (id) => document.getElementById(id);

function showAlert(message, type = "danger") {
    $("alertArea").innerHTML = `
        <div class="alert alert-${type} alert-dismissible">
            ${message}
            <button class="btn-close" data-bs-dismiss="alert"></button>
        </div>`;
}

function formatBytes(bytes) {
    if (!bytes) return "0 B";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0;
    let value = bytes;
    while (value >= 1024 && i < units.length - 1) {
        value /= 1024;
        i++;
    }
    return `${value.toFixed(1)} ${units[i]}`;
}

async function checkStatus() {
    const response = await fetch("/api/status");
    const data = await response.json();

    $("ffmpegStatus").textContent = data.ffmpeg
        ? "FFmpeg OK"
        : "FFmpeg não encontrado";

    $("ffmpegStatus").className = data.ffmpeg
        ? "badge text-bg-success"
        : "badge text-bg-danger";
}

async function loadLibrary() {
    const path = $("folderPath").value.trim();

    if (!path) {
        showAlert("Informe o caminho de uma pasta.");
        return;
    }

    try {
        const response = await fetch("/api/library", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({path})
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error);
        }

        renderLibrary(data.files);
        renderSecondaryLibraryLists(data.files);
        $("libraryInfo").textContent =
            `${data.files.length} arquivo(s) encontrado(s)`;
    } catch (error) {
        showAlert(error.message);
    }
}

function renderLibrary(files) {
    const list = $("libraryList");
    list.innerHTML = "";

    if (!files.length) {
        list.innerHTML =
            `<div class="small-muted p-3">Nenhuma música encontrada.</div>`;
        return;
    }

    files.forEach(file => {
        const item = document.createElement("button");
        item.className = "list-group-item list-group-item-action library-item";
        item.style.background = "transparent";
        item.style.color = "#e5e7eb";

        const mediaBadge = file.is_video
            ? '<span class="badge text-bg-primary ms-1">VÍDEO</span>'
            : '';

        item.innerHTML = `
            <div class="fw-semibold">
                ${escapeHtml(file.title)} ${mediaBadge}
            </div>
            <div class="small-muted">
                ${escapeHtml(file.artist || "Artista desconhecido")}
                · ${file.duration_formatted}
                · ${formatBytes(file.size)}
            </div>
        `;

        item.addEventListener("click", () => selectTrack(file));
        list.appendChild(item);
    });
}

function renderSecondaryLibraryLists(files) {
    const list = $("karaokeLibraryList");
    if (!list) return;
    list.innerHTML = "";
    files.forEach(file => {
        const item = document.createElement("button");
        item.className = "list-group-item list-group-item-action library-item";
        item.style.background = "transparent";
        item.style.color = "#e5e7eb";
        const badge = file.is_video ? '<span class="badge text-bg-primary ms-1">VÍDEO</span>' : "";
        item.innerHTML = `<div class="fw-semibold">${escapeHtml(file.title)} ${badge}</div>
        <div class="small-muted">${escapeHtml(file.artist || "Artista desconhecido")} · ${file.duration_formatted} · ${formatBytes(file.size)}</div>`;
        item.addEventListener("click", () => selectTrack(file));
        list.appendChild(item);
    });
}

async function selectTrack(file) {
    currentTrack = file;

    $("emptyEditor").classList.add("d-none");
    $("editor").classList.remove("d-none");

    $("trackTitle").textContent = file.title;
    $("trackMeta").textContent =
        `${file.artist || "Artista desconhecido"} · ${file.extension} · ${file.bitrate_formatted || ""}` +
        (file.is_video ? " · faixa de áudio do vídeo" : "");

    $("audioPlayer").src =
        `/api/stream?path=${encodeURIComponent(file.path)}`;

    if (file.is_video) {
        valueOf("outputFormat") = "mp4";
    } else if (valueOf("outputFormat") === "mp4") {
        valueOf("outputFormat") = "mp3";
    }

    valueOf("startSeconds") = 0;
    valueOf("endSeconds") = file.duration;

    createWaveform(file);

    try {
        const response = await fetch(
            `/api/audio?path=${encodeURIComponent(file.path)}`
        );
        const data = await response.json();

        if (!response.ok) throw new Error(data.error);

        valueOf("endSeconds") = data.duration;
    } catch (error) {
        console.error(error);
    }
}

function createWaveform(file) {
    if (wave) {
        wave.destroy();
        wave = null;
    }

    const audioElement = $("audioPlayer");

    // WaveSurfer usa o mesmo elemento <audio> do player principal.
    // Assim evitamos duas instancias reproduzindo o mesmo arquivo.
    wave = WaveSurfer.create({
        container: "#waveform",
        waveColor: "#6b7280",
        progressColor: "#60a5fa",
        cursorColor: "#f9fafb",
        height: 180,
        normalize: true,
        media: audioElement
    });

    wave.load(
        `/api/stream?path=${encodeURIComponent(file.path)}`
    );

    wave.on("error", (error) => {
        console.error("WaveSurfer:", error);
        showAlert(
            "Não foi possível carregar o áudio para a visualização. " +
            "O player HTML continuará sendo usado."
        );
    });

    wave.on("interaction", (newTime) => {
        audioElement.currentTime = newTime;
    });
}

$("useSelection")?.addEventListener("click", () => {
    if (!wave) return;

    const duration = wave.getDuration();
    const current = wave.getCurrentTime();

    valueOf("startSeconds") = Math.max(0, current - 5).toFixed(2);
    valueOf("endSeconds") = Math.min(duration, current + 5).toFixed(2);
});

$("exportButton")?.addEventListener("click", async () => {
    if (!currentTrack) return;

    const button = $("exportButton");
    button.disabled = true;
    button.textContent = "Processando...";

    const payload = {
        source: currentTrack.path,
        start_ms: Math.round(parseFloat(valueOf("startSeconds") || 0) * 1000),
        end_ms: Math.round(parseFloat(valueOf("endSeconds") || currentTrack.duration) * 1000),
        volume_db: parseFloat(valueOf("volumeDb") || 0),
        fade_in_ms: parseInt(valueOf("fadeIn") || 0),
        fade_out_ms: parseInt(valueOf("fadeOut") || 0),
        action: "export",
        output_format: valueOf("outputFormat"),
        bitrate: valueOf("bitrate")
    };

    try {
        const response = await fetch("/api/process", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error);
        }

        $("exportResult").innerHTML = `
            <div class="alert alert-success">
                Edição concluída.
                <a class="alert-link"
                   href="${data.download_url}">
                   Baixar arquivo
                </a>
            </div>`;
    } catch (error) {
        $("exportResult").innerHTML = `
            <div class="alert alert-danger">${escapeHtml(error.message)}</div>`;
    } finally {
        button.disabled = false;
        button.textContent = "Exportar edição";
    }
});

$("loadLibrary").addEventListener("click", loadLibrary);

$("folderPath").addEventListener("keydown", (event) => {
    if (event.key === "Enter") loadLibrary();
});

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

checkStatus();

function bindBatchRange(id, label, suffix) {
    const input = $(id), output = $(label);
    const update = () => output.textContent = `${input.value}${suffix}`;
    input.addEventListener("input", update);
    update();
}
bindBatchRange("batchBass", "batchBassValue", " dB");
bindBatchRange("batchMid", "batchMidValue", " dB");
bindBatchRange("batchTreble", "batchTrebleValue", " dB");
bindBatchRange("batchIntensity", "batchIntensityValue", "%");
bindBatchRange("batchVolume", "batchVolumeValue", " dB");

$("batchProcess").addEventListener("click", async () => {
    const folder = $("folderPath").value.trim();
    if (!folder) {
        showAlert("Carregue uma pasta antes de aplicar o ajuste em lote.");
        return;
    }

    const button = $("batchProcess");
    button.disabled = true;
    button.textContent = "Processando...";
    $("batchResult").innerHTML = '<div class="alert alert-info">Processando os arquivos...</div>';

    try {
        const response = await fetch("/api/batch", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                folder,
                bass_db: parseFloat($("batchBass").value),
                mid_db: parseFloat($("batchMid").value),
                treble_db: parseFloat($("batchTreble").value),
                intensity: parseFloat($("batchIntensity").value),
                volume_db: parseFloat($("batchVolume").value),
                output_format: $("batchFormat").value,
                bitrate: valueOf("bitrate"),
                mode: $("batchMode").value
            })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error);

        $("batchResult").innerHTML = `
            <div class="alert alert-success">
                ${data.processed.length} arquivo(s) processado(s).
                ${data.failed.length ? `<br>${data.failed.length} arquivo(s) com erro.` : ""}
                <br><span class="small-muted">${escapeHtml(data.output_dir)}</span>
            </div>`;
    } catch (error) {
        $("batchResult").innerHTML = `<div class="alert alert-danger">${escapeHtml(error.message)}</div>`;
    } finally {
        button.disabled = false;
        button.textContent = "Aplicar em toda a pasta";
    }
});


// ============================================================
// Pré-visualização de áudio em tempo real
// ============================================================

let previewAudioContext = null;
let previewSource = null;
let previewLow = null;
let previewMid = null;
let previewHigh = null;
let previewCompressor = null;
let previewGain = null;
let previewEnabled = false;

function setPreviewStatus(message, type = "secondary") {
    const status = $("previewStatus");
    if (!status) return;
    status.className = `alert alert-${type} py-2`;
    status.textContent = message;
}

function initPreviewAudio() {
    if (previewAudioContext) return;

    const AudioContextClass =
        window.AudioContext || window.webkitAudioContext;

    if (!AudioContextClass) {
        setPreviewStatus(
            "Este navegador não oferece Web Audio API.",
            "warning"
        );
        return;
    }

    previewAudioContext = new AudioContextClass();

    // O mesmo elemento <audio> usado pelo player é conectado à cadeia DSP.
    // Assim a prévia não cria um segundo player.
    previewSource = previewAudioContext.createMediaElementSource(
        $("audioPlayer")
    );

    previewLow = previewAudioContext.createBiquadFilter();
    previewLow.type = "lowshelf";
    previewLow.frequency.value = 100;

    previewMid = previewAudioContext.createBiquadFilter();
    previewMid.type = "peaking";
    previewMid.frequency.value = 1000;
    previewMid.Q.value = 1;

    previewHigh = previewAudioContext.createBiquadFilter();
    previewHigh.type = "highshelf";
    previewHigh.frequency.value = 8000;

    previewCompressor = previewAudioContext.createDynamicsCompressor();
    previewCompressor.attack.value = 0.02;
    previewCompressor.release.value = 0.18;

    previewGain = previewAudioContext.createGain();

    previewSource
        .connect(previewLow)
        .connect(previewMid)
        .connect(previewHigh)
        .connect(previewCompressor)
        .connect(previewGain)
        .connect(previewAudioContext.destination);

    previewEnabled = true;
    updatePreviewFilters();
}

async function resumePreviewAudio() {
    initPreviewAudio();

    if (
        previewAudioContext &&
        previewAudioContext.state === "suspended"
    ) {
        await previewAudioContext.resume();
    }
}

function updatePreviewFilters() {
    if (!previewEnabled || !previewAudioContext) return;

    const now = previewAudioContext.currentTime;

    const bass = parseFloat($("batchBass").value || 0);
    const mid = parseFloat($("batchMid").value || 0);
    const treble = parseFloat($("batchTreble").value || 0);
    const intensity = parseFloat($("batchIntensity").value || 0);
    const volume = parseFloat($("batchVolume").value || 0);

    // Timbre.
    previewLow.gain.setTargetAtTime(bass, now, 0.015);
    previewMid.gain.setTargetAtTime(mid, now, 0.015);
    previewHigh.gain.setTargetAtTime(treble, now, 0.015);

    // Intensidade = compressão dinâmica.
    const normalized = intensity / 100;

    previewCompressor.threshold.setTargetAtTime(
        -18 - normalized * 10,
        now,
        0.015
    );

    previewCompressor.ratio.setTargetAtTime(
        1 + normalized * 4,
        now,
        0.015
    );

    // Volume em dB convertido para ganho linear.
    const linearGain = Math.pow(10, volume / 20);

    previewGain.gain.setTargetAtTime(
        linearGain,
        now,
        0.015
    );
}

// Ativação automática ao apertar Play.
$("audioPlayer").addEventListener("play", async () => {
    try {
        await resumePreviewAudio();

        if (currentTrack) {
            setPreviewStatus(
                `Prévia ativa: ${currentTrack.title}`,
                "success"
            );
        }
    } catch (error) {
        console.error(error);
        setPreviewStatus(
            "Não foi possível ativar a prévia.",
            "danger"
        );
    }
});

// Alterações nos controles são aplicadas imediatamente.
[
    "batchBass",
    "batchMid",
    "batchTreble",
    "batchIntensity",
    "batchVolume"
].forEach(id => {
    $(id).addEventListener("input", updatePreviewFilters);
});

$("previewEnable").addEventListener("click", async () => {
    if (!currentTrack) {
        showAlert("Selecione uma música antes de ativar a prévia.");
        return;
    }

    try {
        await resumePreviewAudio();
        updatePreviewFilters();

        setPreviewStatus(
            `Prévia ativada para: ${currentTrack.title}`,
            "success"
        );
    } catch (error) {
        console.error(error);
        setPreviewStatus(
            "Não foi possível ativar a prévia.",
            "danger"
        );
    }
});

$("previewReset").addEventListener("click", () => {
    $("batchBass").value = 0;
    $("batchMid").value = 0;
    $("batchTreble").value = 0;
    $("batchIntensity").value = 0;
    $("batchVolume").value = 0;

    [
        "batchBass",
        "batchMid",
        "batchTreble",
        "batchIntensity",
        "batchVolume"
    ].forEach(id => {
        $(id).dispatchEvent(new Event("input"));
    });

    updatePreviewFilters();

    if (currentTrack) {
        setPreviewStatus(
            `Prévia restaurada: ${currentTrack.title}`,
            "secondary"
        );
    }
});

let folderAnalysis=null;
function bindLevelRange(id,label,suffix){
 const a=$(id),b=$(label); const u=()=>b.textContent=`${a.value}${suffix}`;
 a.addEventListener("input",u);u();
}
bindLevelRange("targetLufs","targetLufsValue"," LUFS");
bindLevelRange("targetLra","targetLraValue"," LU");

$("analyzeFolder").addEventListener("click",async()=>{
 const folder=$("folderPath").value.trim(); if(!folder){showAlert("Informe uma pasta.");return;}
 const b=$("analyzeFolder");b.disabled=true;b.textContent="Analisando...";
 $("analysisResult").innerHTML='<div class="alert alert-info">Analisando arquivos...</div>';
 try{
  const r=await fetch("/api/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({folder})});
  const x=await r.json();if(!r.ok)throw new Error(x.error);folderAnalysis=x;
  $("targetLufs").value=x.recommended.lufs;$("targetLra").value=x.recommended.lra;
  $("targetLufs").dispatchEvent(new Event("input"));$("targetLra").dispatchEvent(new Event("input"));
  $("analysisResult").innerHTML=`<div class="row g-2">
  <div class="col-4"><div class="border rounded p-2 text-center"><div class="small-muted">Volume médio</div><strong>${x.average.lufs} LUFS</strong></div></div>
  <div class="col-4"><div class="border rounded p-2 text-center"><div class="small-muted">Intensidade média</div><strong>${x.average.lra} LU</strong></div></div>
  <div class="col-4"><div class="border rounded p-2 text-center"><div class="small-muted">True Peak</div><strong>${x.average.true_peak} dBTP</strong></div></div></div>
  <div class="alert alert-secondary mt-2 mb-0 py-2">A média foi definida como alvo inicial.</div>`;
  $("levelFolder").disabled=false;
 }catch(e){folderAnalysis=null;$("analysisResult").innerHTML=`<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;$("levelFolder").disabled=true;}
 finally{b.disabled=false;b.textContent="Analisar pasta";}
});

$("levelFolder").addEventListener("click",async()=>{
 if(!folderAnalysis){showAlert("Analise a pasta primeiro.");return;}
 const b=$("levelFolder");b.disabled=true;b.textContent="Nivelando...";
 $("levelResult").innerHTML='<div class="alert alert-info">Nivelando arquivos...</div>';
 try{
  const r=await fetch("/api/level",{method:"POST",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({folder:$("folderPath").value.trim(),target_lufs:parseFloat($("targetLufs").value),
   target_lra:parseFloat($("targetLra").value),bitrate:valueOf("bitrate"),
                mode: $("levelMode").value})});
  const x=await r.json();if(!r.ok)throw new Error(x.error);
  $("levelResult").innerHTML=`<div class="alert alert-success"><strong>${x.processed.length}</strong> arquivo(s) nivelado(s).${x.failed.length?`<br>${x.failed.length} com erro.`:""}<br><span class="small-muted">${escapeHtml(x.output_dir)}</span></div>`;
 }catch(e){$("levelResult").innerHTML=`<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;}
 finally{b.disabled=false;b.textContent="Nivelar toda a pasta";}
});


// ============================================================
// Modo Karaoke / transposição
// ============================================================

let karaokeAnalysis=null;
let karaokeFolderAnalysis=null;

function updateKaraokeShiftLabel(){
    const value=parseInt($("karaokeShift").value,10);
    $("karaokeShiftValue").textContent =
        value > 0 ? `+${value} semitons` :
        value < 0 ? `${value} semitons` : "0 semitons";
}
$("karaokeShift").addEventListener("input",updateKaraokeShiftLabel);
updateKaraokeShiftLabel();

function renderKaraokeAnalysis(data){
    const r=data.range;
    const rec=data.recommendation;

    $("karaokeResult").innerHTML=`
    <div class="border rounded p-2">
        <div><strong>Tom estimado:</strong> ${escapeHtml(data.key.name)}
            <span class="small-muted">(${data.key.confidence}% de confiança)</span>
        </div>
        <div><strong>Faixa melódica estimada:</strong>
            ${escapeHtml(r.low.name)} – ${escapeHtml(r.high.name)}
        </div>
        <div><strong>Nota central:</strong> ${escapeHtml(r.median.name)}</div>
        <hr>
        <div><strong>Perfil:</strong> ${escapeHtml(rec.profile_label)}</div>
        <div><strong>Recomendação:</strong>
            ${rec.recommended_semitones > 0 ? "+" : ""}
            ${rec.recommended_semitones} semitons
        </div>
        <div><strong>Compatibilidade estimada:</strong> ${rec.score}%</div>
        <div class="small-muted mt-2">
            A faixa melódica é uma estimativa automática e pode incluir
            instrumentos ou backing vocals. Use seu ouvido para validar.
        </div>
    </div>`;

    $("karaokeShift").value=rec.recommended_semitones;
    updateKaraokeShiftLabel();
    $("karaokeRecommend").disabled=false;
    $("karaokeApplyTrack").disabled=false;
}

$("karaokeAnalyze").addEventListener("click",async()=>{
    if(!currentTrack){
        showAlert("Selecione uma música primeiro.");
        return;
    }

    const b=$("karaokeAnalyze");
    b.disabled=true;b.textContent="Analisando...";
    $("karaokeResult").innerHTML=
        '<div class="alert alert-info">Analisando a faixa melódica...</div>';

    try{
        const r=await fetch("/api/karaoke/analyze",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
                path:currentTrack.path,
                profile:$("karaokeProfile").value
            })
        });
        const data=await r.json();
        if(!r.ok)throw new Error(data.error);
        karaokeAnalysis=data;
        renderKaraokeAnalysis(data);
    }catch(e){
        $("karaokeResult").innerHTML=
            `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }finally{
        b.disabled=false;b.textContent="Analisar música selecionada";
    }
});

$("karaokeRecommend").addEventListener("click",()=>{
    if(!karaokeAnalysis)return;
    $("karaokeShift").value=
        karaokeAnalysis.recommendation.recommended_semitones;
    updateKaraokeShiftLabel();
});

$("karaokeApplyTrack").addEventListener("click",async()=>{
    if(!currentTrack)return;

    const b=$("karaokeApplyTrack");
    b.disabled=true;b.textContent="Processando...";

    try{
        const r=await fetch("/api/karaoke/transpose",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
                path:currentTrack.path,
                semitones:parseInt($("karaokeShift").value,10),
                mode:$("karaokeMode").value,
                bitrate:valueOf("bitrate")
            })
        });
        const data=await r.json();
        if(!r.ok)throw new Error(data.error);

        $("karaokeResult").insertAdjacentHTML("beforeend",
            `<div class="alert alert-success mt-2">
                Transposição aplicada: ${data.semitones > 0 ? "+" : ""}
                ${data.semitones} semitons.
                ${data.mode==="replace"
                    ? "O arquivo original foi substituído."
                    : "Um novo arquivo foi criado."}
            </div>`);
    }catch(e){
        $("karaokeResult").insertAdjacentHTML("beforeend",
            `<div class="alert alert-danger mt-2">${escapeHtml(e.message)}</div>`);
    }finally{
        b.disabled=false;b.textContent="Aplicar à música";
    }
});

$("karaokeAnalyzeFolder").addEventListener("click",async()=>{
    const folder=$("folderPath").value.trim();
    if(!folder){showAlert("Informe uma pasta.");return;}

    const b=$("karaokeAnalyzeFolder");
    b.disabled=true;b.textContent="Analisando pasta...";
    $("karaokeFolderResult").innerHTML=
        '<div class="alert alert-info">Analisando as músicas...</div>';

    try{
        const r=await fetch("/api/karaoke/analyze",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
                path:folder,
                profile:$("karaokeProfile").value
            })
        });
        const data=await r.json();
        if(!r.ok)throw new Error(data.error);
        karaokeFolderAnalysis=data;

        const rows=data.files.map(x=>`
            <tr>
                <td>${escapeHtml(x.name)}</td>
                <td>${escapeHtml(x.key.name)}</td>
                <td>${escapeHtml(x.range.low.name)} – ${escapeHtml(x.range.high.name)}</td>
                <td>${x.recommendation.recommended_semitones>0?"+":""}${x.recommendation.recommended_semitones}</td>
                <td>${x.recommendation.score}%</td>
            </tr>`).join("");

        $("karaokeFolderResult").innerHTML=`
        <div class="small-muted mb-2">
            ${data.count} arquivo(s) analisado(s).
            ${data.failed_count?`${data.failed_count} não puderam ser analisados.`:""}
        </div>
        <div class="table-responsive" style="max-height:300px">
        <table class="table table-sm table-dark align-middle">
        <thead><tr><th>Música</th><th>Tom</th><th>Faixa</th><th>Semitons</th><th>Compat.</th></tr></thead>
        <tbody>${rows}</tbody>
        </table></div>
        <button id="karaokeApplyFolder" class="btn btn-success w-100">
            Aplicar recomendações à pasta
        </button>`;

        $("karaokeApplyFolder")?.addEventListener("click",applyKaraokeFolder);
    }catch(e){
        $("karaokeFolderResult").innerHTML=
            `<div class="alert alert-danger">${escapeHtml(e.message)}</div>`;
    }finally{
        b.disabled=false;b.textContent="Analisar toda a pasta";
    }
});

async function applyKaraokeFolder(){
    if(!karaokeFolderAnalysis)return;

    const shifts={};
    karaokeFolderAnalysis.files.forEach(x=>{
        shifts[x.path]=x.recommendation.recommended_semitones;
    });

    const b=$("karaokeApplyFolder");
    b.disabled=true;b.textContent="Processando pasta...";

    try{
        const r=await fetch("/api/karaoke/transpose",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({
                path:$("folderPath").value.trim(),
                semitones_map:shifts,
                mode:$("karaokeMode").value,
                bitrate:valueOf("bitrate")
            })
        });
        const data=await r.json();
        if(!r.ok)throw new Error(data.error);

        $("karaokeFolderResult").insertAdjacentHTML("beforeend",
            `<div class="alert alert-success mt-2">
                ${data.processed.length} arquivo(s) transposto(s).
                ${data.failed.length?`<br>${data.failed.length} com erro.`:""}
                <br>${data.mode==="replace"
                    ?"Os arquivos originais foram substituídos."
                    :"Novos arquivos foram criados."}
            </div>`);
    }catch(e){
        $("karaokeFolderResult").insertAdjacentHTML("beforeend",
            `<div class="alert alert-danger mt-2">${escapeHtml(e.message)}</div>`);
    }finally{
        b.disabled=false;b.textContent="Aplicar recomendações à pasta";
    }
}


// Fallback para navegação das abas.
// Bootstrap 5 continua sendo usado quando disponível; este código garante
// navegação básica mesmo quando o JS do CDN não estiver acessível.
document.addEventListener("DOMContentLoaded", () => {
    const tabButtons = document.querySelectorAll('[data-bs-toggle="tab"]');

    tabButtons.forEach(button => {
        button.addEventListener("click", () => {
            const targetSelector = button.getAttribute("data-bs-target");
            const target = targetSelector
                ? document.querySelector(targetSelector)
                : null;

            if (!target) return;

            tabButtons.forEach(btn => {
                btn.classList.remove("active");
                btn.setAttribute("aria-selected", "false");
            });

            document.querySelectorAll(".tab-pane").forEach(pane => {
                pane.classList.remove("show", "active");
            });

            button.classList.add("active");
            button.setAttribute("aria-selected", "true");
            target.classList.add("show", "active");
        });
    });
});

function valueOf(id, fallback="") {
    const el=$(id);
    return el ? el.value : fallback;
}

function setValueIfPresent(id, value) {
    const el=$(id);
    if (el) el.value=value;
}



// ============================================================
// V15 — Aparência e identidade
// ============================================================

let appSettings = null;

const DEFAULT_APP_SETTINGS = {
    identity: {
        title: "Audio Editor Local",
        subtitle: "Editor de músicas executado no próprio computador",
        logo_type: "emoji",
        logo_value: "🎵"
    },
    appearance: {
        theme: "dark",
        primary: "#6C63FF",
        secondary: "#252936",
        background: "#111318",
        card: "#1B1E27",
        text: "#F5F7FA",
        muted: "#9CA3AF",
        accent: "#00D4FF",
        font_size: "normal",
        density: "normal",
        border_radius: 10
    }
};

function applySettings(settings) {
    appSettings = settings || DEFAULT_APP_SETTINGS;
    const i = appSettings.identity || DEFAULT_APP_SETTINGS.identity;
    const a = appSettings.appearance || DEFAULT_APP_SETTINGS.appearance;
    const root = document.documentElement;

    root.style.setProperty("--app-primary", a.primary);
    root.style.setProperty("--app-secondary", a.secondary);
    root.style.setProperty("--app-background", a.background);
    root.style.setProperty("--app-card", a.card);
    root.style.setProperty("--app-text", a.text);
    root.style.setProperty("--app-muted", a.muted || DEFAULT_APP_SETTINGS.appearance.muted);
    root.style.setProperty("--app-accent", a.accent);
    root.style.setProperty("--app-success", a.success || "#22C55E");
    root.style.setProperty("--app-danger", a.danger || "#EF4444");
    root.style.setProperty("--app-warning", a.warning || "#F59E0B");
    root.style.setProperty("--app-radius", `${a.border_radius ?? 10}px`);

    document.body.classList.remove("font-small","font-large","density-compact","density-spacious");
    if (a.font_size === "small") document.body.classList.add("font-small");
    if (a.font_size === "large") document.body.classList.add("font-large");
    if (a.density === "compact") document.body.classList.add("density-compact");
    if (a.density === "spacious") document.body.classList.add("density-spacious");

    const title = $("appTitle");
    const subtitle = $("appSubtitle");
    const logo = $("appLogo");
    if (title) title.textContent = i.title || DEFAULT_APP_SETTINGS.identity.title;
    if (subtitle) subtitle.textContent = i.subtitle || DEFAULT_APP_SETTINGS.identity.subtitle;

    if (logo) {
        logo.textContent = i.logo_type === "none" ? "" : (i.logo_value || "🎵");
        logo.style.display = i.logo_type === "none" ? "none" : "flex";
    }

    document.title = i.title || DEFAULT_APP_SETTINGS.identity.title;
    updateSettingsForm(appSettings);
    updateSettingsPreview(appSettings);
}

function updateSettingsForm(settings) {
    const i = settings.identity;
    const a = settings.appearance;
    setValueIfPresent("settingsTitle", i.title);
    setValueIfPresent("settingsSubtitle", i.subtitle);
    setValueIfPresent("settingsLogoType", i.logo_type);
    setValueIfPresent("settingsLogoValue", i.logo_value);
    setValueIfPresent("settingsTheme", a.theme);
    setValueIfPresent("settingsPrimary", a.primary);
    setValueIfPresent("settingsSecondary", a.secondary);
    setValueIfPresent("settingsAccent", a.accent);
    setValueIfPresent("settingsBackground", a.background);
    setValueIfPresent("settingsCard", a.card);
    setValueIfPresent("settingsText", a.text);
    setValueIfPresent("settingsFontSize", a.font_size);
    setValueIfPresent("settingsDensity", a.density);
    setValueIfPresent("settingsRadius", a.border_radius);
    const radius = $("settingsRadiusValue");
    if (radius) radius.textContent = a.border_radius;
}

function updateSettingsPreview(settings) {
    const i = settings.identity;
    const a = settings.appearance;
    const root = document.documentElement;
    const logo = $("previewLogo");
    const title = $("previewTitle");
    const subtitle = $("previewSubtitle");
    const preview = $("themePreview");

    if (logo) {
        logo.textContent = i.logo_type === "none" ? "" : (i.logo_value || "🎵");
        logo.style.display = i.logo_type === "none" ? "none" : "flex";
    }
    if (title) title.textContent = i.title;
    if (subtitle) subtitle.textContent = i.subtitle;
    if (preview) {
        preview.style.background = a.background;
        preview.style.color = a.text;
    }

    root.style.setProperty("--app-primary", a.primary);
    root.style.setProperty("--app-secondary", a.secondary);
    root.style.setProperty("--app-background", a.background);
    root.style.setProperty("--app-card", a.card);
    root.style.setProperty("--app-text", a.text);
    root.style.setProperty("--app-radius", `${a.border_radius}px`);
}

function collectSettingsFromForm() {
    const current = appSettings || structuredClone(DEFAULT_APP_SETTINGS);
    return {
        identity: {
            ...current.identity,
            title: valueOf("settingsTitle", current.identity.title),
            subtitle: valueOf("settingsSubtitle", current.identity.subtitle),
            logo_type: valueOf("settingsLogoType", current.identity.logo_type),
            logo_value: valueOf("settingsLogoValue", current.identity.logo_value)
        },
        appearance: {
            ...current.appearance,
            theme: valueOf("settingsTheme", current.appearance.theme),
            primary: valueOf("settingsPrimary", current.appearance.primary),
            secondary: valueOf("settingsSecondary", current.appearance.secondary),
            accent: valueOf("settingsAccent", current.appearance.accent),
            background: valueOf("settingsBackground", current.appearance.background),
            card: valueOf("settingsCard", current.appearance.card),
            text: valueOf("settingsText", current.appearance.text),
            font_size: valueOf("settingsFontSize", current.appearance.font_size),
            density: valueOf("settingsDensity", current.appearance.density),
            border_radius: Number(valueOf("settingsRadius", current.appearance.border_radius))
        }
    };
}

async function loadAppSettings() {
    try {
        const response = await fetch("/api/settings");
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Erro ao carregar configurações.");
        applySettings(data);
    } catch (error) {
        applySettings(DEFAULT_APP_SETTINGS);
        console.warn("Configurações visuais:", error);
    }
}

async function saveAppSettings() {
    const button = $("saveSettings");
    const result = $("settingsResult");
    if (button) button.disabled = true;

    try {
        const data = collectSettingsFromForm();
        const response = await fetch("/api/settings", {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify(data)
        });
        const saved = await response.json();
        if (!response.ok) throw new Error(saved.error || "Erro ao salvar.");
        applySettings(saved);
        if (result) result.innerHTML = '<div class="alert alert-success py-2">Aparência salva.</div>';
    } catch (error) {
        if (result) result.innerHTML = `<div class="alert alert-danger py-2">${escapeHtml(error.message)}</div>`;
    } finally {
        if (button) button.disabled = false;
    }
}

async function resetAppSettings() {
    if (!confirm("Restaurar a aparência e identidade padrão?")) return;
    try {
        const response = await fetch("/api/settings/reset", {method:"POST"});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Erro ao restaurar.");
        applySettings(data);
        const result = $("settingsResult");
        if (result) result.innerHTML = '<div class="alert alert-success py-2">Padrões restaurados.</div>';
    } catch (error) {
        const result = $("settingsResult");
        if (result) result.innerHTML = `<div class="alert alert-danger py-2">${escapeHtml(error.message)}</div>`;
    }
}

function previewSettingsLive() {
    try {
        const settings = collectSettingsFromForm();
        updateSettingsPreview(settings);
    } catch (_) {}
}

document.addEventListener("DOMContentLoaded", () => {
    loadAppSettings();

    $("saveSettings")?.addEventListener("click", saveAppSettings);
    $("resetSettings")?.addEventListener("click", resetAppSettings);
    $("settingsRadius")?.addEventListener("input", () => {
        const value = $("settingsRadius").value;
        if ($("settingsRadiusValue")) $("settingsRadiusValue").textContent = value;
        previewSettingsLive();
    });

    [
        "settingsTitle","settingsSubtitle","settingsLogoType","settingsLogoValue",
        "settingsTheme","settingsPrimary","settingsSecondary","settingsAccent",
        "settingsBackground","settingsCard","settingsText",
        "settingsFontSize","settingsDensity"
    ].forEach(id => {
        $(id)?.addEventListener("input", previewSettingsLive);
        $(id)?.addEventListener("change", previewSettingsLive);
    });
});
