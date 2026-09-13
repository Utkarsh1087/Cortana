/**
 * Lisa — Ultra-Enhanced 3D Humanoid Avatar & Neural Viseme Engine
 * High-Fidelity Three.js Humanoid Mesh, PBR Subsurface Shaders, ARKit Lipsync & Studio HDRI
 */

// -------------------------------------------------------------
// 1. State & Tracking
// -------------------------------------------------------------
let currentState = 'idle';
let currentEmotion = 'affectionate';
let currentPreset = 'classic';
let audioEnergy = 0.0;

// Gaze & Tracking
let targetGazeX = 0;
let targetGazeY = 0;
let currentGazeX = 0;
let currentGazeY = 0;
let eyeSaccadeX = 0;
let eyeSaccadeY = 0;
let saccadeTimer = 0;

// Blinking & Micro-Expressions
let blinkTimer = 0;
let isBlinking = false;
let blinkProgress = 0.0;
let nextBlinkInterval = 3.4;
let nodProgress = 0.0;
let isNodding = false;

// Custom 3D Avatar (FBX / GLTF / ReadyPlayerMe) Tracking
let loadedCustomAvatar = null;
let customMorphMeshes = [];
let customBones = {};
let customAnimationMixer = null;
let customBaseMaterial = null;
let customModelLoaded = false;
let customModelBaseY = -1.45;

// Mocap Animation Repertoire & State
const MOCAP_ANIMATION_MAP = {
    // Idles
    'idle': '/static/models/animations/Happy Idle.fbx',
    'happy idle': '/static/models/animations/Happy Idle.fbx',
    'sad idle': '/static/models/animations/Sad Idle.fbx',
    
    // Conversations & Speech
    'talking': '/static/models/animations/Talking.fbx',
    'talking 1': '/static/models/animations/Talking (1).fbx',
    'talking 2': '/static/models/animations/Talking (2).fbx',
    'talking 3': '/static/models/animations/Talking (3).fbx',
    'talking 4': '/static/models/animations/Talking (4).fbx',
    
    // Greetings & Gestures
    'wave': '/static/models/animations/Waving.fbx',
    'waving': '/static/models/animations/Waving.fbx',
    'bow': '/static/models/animations/Quick Formal Bow.fbx',
    'acknowledging': '/static/models/animations/acknowledging.fbx',
    'head nod': '/static/models/animations/head nod yes.fbx',
    'hard nod': '/static/models/animations/hard head nod.fbx',
    'lengthy nod': '/static/models/animations/lengthy head nod.fbx',
    'sarcastic nod': '/static/models/animations/sarcastic head nod.fbx',
    'shake head': '/static/models/animations/shaking head no.fbx',
    'shake head no': '/static/models/animations/shaking head no.fbx',
    'annoyed shake': '/static/models/animations/annoyed head shake.fbx',
    'thoughtful shake': '/static/models/animations/thoughtful head shake.fbx',

    // Emotions & Expressions
    'laugh': '/static/models/animations/Laughing.fbx',
    'laughing': '/static/models/animations/Laughing.fbx',
    'clap': '/static/models/animations/Clapping.fbx',
    'clapping': '/static/models/animations/Clapping.fbx',
    'cry': '/static/models/animations/Crying.fbx',
    'crying': '/static/models/animations/Crying.fbx',
    'excited': '/static/models/animations/Excited.fbx',
    'happy': '/static/models/animations/Happy.fbx',
    'happy hands': '/static/models/animations/happy hand gesture.fbx',
    'angry': '/static/models/animations/Angry.fbx',
    'angry gesture': '/static/models/animations/angry gesture.fbx',
    'angry point': '/static/models/animations/Angry Point.fbx',
    'yelling': '/static/models/animations/Yelling.fbx',
    'argue': '/static/models/animations/Standing Arguing.fbx',
    'arguing': '/static/models/animations/Standing Arguing.fbx',
    'disappointed': '/static/models/animations/Disappointed.fbx',
    'rejected': '/static/models/animations/Rejected.fbx',
    'relieved sigh': '/static/models/animations/relieved sigh.fbx',
    'cocky': '/static/models/animations/being cocky.fbx',
    'being cocky': '/static/models/animations/being cocky.fbx',
    'dismissing': '/static/models/animations/dismissing gesture.fbx',
    'dismissing gesture': '/static/models/animations/dismissing gesture.fbx',
    'look away': '/static/models/animations/look away gesture.fbx',
    'weight shift': '/static/models/animations/weight shift.fbx',
    'turn': '/static/models/animations/Happy Right Turn.fbx',

    // Dances & Choreography
    'salsa': '/static/models/animations/Salsa Dancing.fbx',
    'salsa dance': '/static/models/animations/Salsa Dancing.fbx',
    'salsa dancing': '/static/models/animations/Salsa Dancing.fbx',
    'moonwalk': '/static/models/animations/Moonwalk.fbx',
    'hip hop': '/static/models/animations/Hip Hop Dancing.fbx',
    'hip hop dance': '/static/models/animations/Hip Hop Dancing.fbx',
    'locking': '/static/models/animations/Locking Hip Hop Dance.fbx',
    'tutting': '/static/models/animations/Tut Hip Hop Dance.fbx',
    'tut hip hop': '/static/models/animations/Tut Hip Hop Dance.fbx',
    'snake dance': '/static/models/animations/Snake Hip Hop Dance.fbx',
    'wave dance': '/static/models/animations/Wave Hip Hop Dance.fbx',
    'step dance': '/static/models/animations/Step Hip Hop Dance.fbx',
    'chicken dance': '/static/models/animations/Chicken Dance.fbx',
    'swing dance': '/static/models/animations/Swing Dancing.fbx',
    'thriller': '/static/models/animations/Thriller Part 3.fbx',
    'thriller dance': '/static/models/animations/Thriller Part 3.fbx',
    'soul spin': '/static/models/animations/Northern Soul Spin Combo.fbx',
    'dance pose': '/static/models/animations/Female Dance Pose.fbx',
    'flair': '/static/models/animations/Flair.fbx',
    
    // Breakdance Styles
    'breakdance': '/static/models/animations/Breakdance Freezes.fbx',
    'breakdance 1990': '/static/models/animations/breakdance 1990.fbx',
    'breakdance freeze': '/static/models/animations/Breakdance Freeze Var 4.fbx',
    'breakdance footwork': '/static/models/animations/breakdance footwork 1.fbx',
    'breakdance swipes': '/static/models/animations/breakdance swipes.fbx',
    'breakdance uprock': '/static/models/animations/breakdance uprock.fbx',
    'brooklyn uprock': '/static/models/animations/brooklyn uprock.fbx',
    'crossleg freeze': '/static/models/animations/crossleg freeze.fbx'
};

const animationClips = {};
const animationActions = {};
let currentMocapAction = null;
let idleMocapAction = null;
let isMocapPlaying = false;
const animFBXLoader = new THREE.FBXLoader();

// Dynamic Gesture System
let currentGesture = null;
let gestureStartTime = 0;
let gestureDuration = 3500;

// -------------------------------------------------------------
// 2. Scene, Perspective Camera & Cinematic Studio Lighting
// -------------------------------------------------------------
const container = document.getElementById('canvas-container');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x06080d);

const camera = new THREE.PerspectiveCamera(36, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 0.18, 3.4);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.25;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

// OrbitControls (Smooth mouse rotation & zoom)
let controls = null;
if (typeof THREE.OrbitControls !== 'undefined') {
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI / 2 + 0.15;
    controls.minDistance = 0.6;
    controls.maxDistance = 6.0;
    controls.target.set(0, -0.05, 0);
}

// HDRI Studio Lighting Simulation
const pmremGenerator = new THREE.PMREMGenerator(renderer);
pmremGenerator.compileEquirectangularShader();

const envCanvas = document.createElement('canvas');
envCanvas.width = 512;
envCanvas.height = 256;
const ectx = envCanvas.getContext('2d');
ectx.fillStyle = '#080a12';
ectx.fillRect(0, 0, 512, 256);

// Overhead Softbox
const grad = ectx.createRadialGradient(256, 60, 5, 256, 60, 180);
grad.addColorStop(0.0, '#ffffff');
grad.addColorStop(0.5, '#90b4d8');
grad.addColorStop(1.0, '#080a12');
ectx.fillStyle = grad;
ectx.fillRect(0, 0, 512, 140);

const envTex = new THREE.CanvasTexture(envCanvas);
const envMap = pmremGenerator.fromEquirectangular(envTex).texture;
scene.environment = envMap;

// 3-Point Studio Portrait Lights
const ambientLight = new THREE.AmbientLight(0xe2e8f0, 1.4);
scene.add(ambientLight);

// Key Light (Warm softbox from top-right)
const keyLight = new THREE.DirectionalLight(0xfff5ea, 2.4);
keyLight.position.set(2.8, 3.2, 2.6);
keyLight.castShadow = true;
keyLight.shadow.mapSize.width = 2048;
keyLight.shadow.mapSize.height = 2048;
keyLight.shadow.bias = -0.0001;
scene.add(keyLight);

// Fill Light (Subtle cool sky fill from top-left)
const fillLight = new THREE.DirectionalLight(0xa5c9eb, 1.6);
fillLight.position.set(-2.8, 1.8, 2.0);
scene.add(fillLight);

// Rim / Halo Light (Highlighting hair silhouette & shoulders)
const rimLight = new THREE.PointLight(0xff7096, 4.2, 18);
rimLight.position.set(0, 2.2, -2.4);
scene.add(rimLight);

// Under Chin Fill
const chinFill = new THREE.PointLight(0xffdfd3, 0.9, 6);
chinFill.position.set(0, -1.5, 1.4);
scene.add(chinFill);

// Atmospheric Sci-Fi Fog
scene.fog = new THREE.FogExp2(0x060812, 0.038);

// -------------------------------------------------------------
// 3. 3D Holographic Cyber Sanctuary Environment
// -------------------------------------------------------------
const environmentGroup = new THREE.Group();
scene.add(environmentGroup);

// A. Holographic Metallic Podium Platform
const podiumGeo = new THREE.CylinderGeometry(1.65, 1.85, 0.12, 48);
const podiumMat = new THREE.MeshStandardMaterial({
    color: 0x0a0e18,
    roughness: 0.3,
    metalness: 0.88,
    envMap: envMap,
    envMapIntensity: 1.0
});
const podiumMesh = new THREE.Mesh(podiumGeo, podiumMat);
podiumMesh.position.y = -1.5;
podiumMesh.receiveShadow = true;
environmentGroup.add(podiumMesh);

// B. Glowing Hologram Floor Rings
const envGlowColor = 0x38bdf8;
const envRingMat = new THREE.MeshBasicMaterial({ color: envGlowColor, transparent: true, opacity: 0.85 });
const podiumRimGeo = new THREE.TorusGeometry(1.82, 0.016, 16, 64);
const podiumRimMesh = new THREE.Mesh(podiumRimGeo, envRingMat);
podiumRimMesh.rotation.x = Math.PI / 2;
podiumRimMesh.position.y = -1.44;
environmentGroup.add(podiumRimMesh);

// C. Dual Rotating Concentric Energy Rings
const outerEnergyRingGeo = new THREE.RingGeometry(2.1, 2.14, 64);
const outerEnergyRingMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, side: THREE.DoubleSide, transparent: true, opacity: 0.55 });
const outerEnergyRing = new THREE.Mesh(outerEnergyRingGeo, outerEnergyRingMat);
outerEnergyRing.rotation.x = Math.PI / 2;
outerEnergyRing.position.y = -1.51;
environmentGroup.add(outerEnergyRing);

const innerEnergyRingGeo = new THREE.RingGeometry(2.45, 2.48, 64);
const innerEnergyRingMat = new THREE.MeshBasicMaterial({ color: 0xf43f5e, side: THREE.DoubleSide, transparent: true, opacity: 0.45 });
const innerEnergyRing = new THREE.Mesh(innerEnergyRingGeo, innerEnergyRingMat);
innerEnergyRing.rotation.x = Math.PI / 2;
innerEnergyRing.position.y = -1.52;
environmentGroup.add(innerEnergyRing);

// D. Cyber Neon Grid Floor
const cyberGrid = new THREE.GridHelper(36, 44, 0x38bdf8, 0x111827);
cyberGrid.position.y = -1.56;
environmentGroup.add(cyberGrid);

// E. Sci-Fi Server Columns / Data Pillars in Background
const pillarGeo = new THREE.BoxGeometry(0.55, 6.5, 0.55);
const pillarMat = new THREE.MeshStandardMaterial({
    color: 0x060911,
    roughness: 0.35,
    metalness: 0.82,
    envMap: envMap
});
const conduitMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.85 });

const pillarPositions = [
    { x: -3.6, z: -4.2, h: 5.5 },
    { x: 3.6, z: -4.2, h: 5.5 },
    { x: -5.6, z: -6.0, h: 7.0 },
    { x: 5.6, z: -6.0, h: 7.0 },
    { x: -2.0, z: -7.2, h: 6.2 },
    { x: 2.0, z: -7.2, h: 6.2 }
];

const pillarConduits = [];

pillarPositions.forEach(pos => {
    const pMesh = new THREE.Mesh(pillarGeo, pillarMat);
    pMesh.scale.set(1, pos.h / 6.5, 1);
    pMesh.position.set(pos.x, pos.h / 2 - 1.56, pos.z);
    pMesh.castShadow = true;
    pMesh.receiveShadow = true;
    environmentGroup.add(pMesh);

    // Glowing vertical neon conduit
    const cGeo = new THREE.BoxGeometry(0.05, pos.h, 0.05);
    const cMesh = new THREE.Mesh(cGeo, conduitMat);
    cMesh.position.set(pos.x, pos.h / 2 - 1.56, pos.z + 0.28);
    environmentGroup.add(cMesh);
    pillarConduits.push(cMesh);
});

// F. Overhead Holographic Halo Arch
const haloGeo = new THREE.TorusGeometry(3.8, 0.022, 16, 64);
const haloMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.45 });
const overheadHalo = new THREE.Mesh(haloGeo, haloMat);
overheadHalo.position.set(0, 3.4, -2.2);
overheadHalo.rotation.x = Math.PI * 0.32;
environmentGroup.add(overheadHalo);

// G. Quantum Starfield / Floating Holographic Dust
const starCount = 800;
const starGeo = new THREE.BufferGeometry();
const starPosArray = new Float32Array(starCount * 3);
const starSpeeds = [];

for (let i = 0; i < starCount; i++) {
    starPosArray[i * 3] = (Math.random() - 0.5) * 16;
    starPosArray[i * 3 + 1] = Math.random() * 8 - 1.5;
    starPosArray[i * 3 + 2] = (Math.random() - 0.5) * 16 - 2;
    starSpeeds.push({
        y: 0.003 + Math.random() * 0.005,
        baseX: starPosArray[i * 3],
        freq: 0.8 + Math.random() * 1.5
    });
}
starGeo.setAttribute('position', new THREE.BufferAttribute(starPosArray, 3));

const starMat = new THREE.PointsMaterial({
    color: 0x93c5fd,
    size: 0.038,
    transparent: true,
    opacity: 0.75,
    blending: THREE.AdditiveBlending
});
const starParticles = new THREE.Points(starGeo, starMat);
environmentGroup.add(starParticles);

// -------------------------------------------------------------
// 4. 3D Avatar Root Container
// -------------------------------------------------------------
const avatarRoot = new THREE.Group();
scene.add(avatarRoot);

// -------------------------------------------------------------
// 5. FBX & GLTF 3D Model Loaders with PBR Textures
// -------------------------------------------------------------
const textureLoader = new THREE.TextureLoader();
const gltfLoader = new THREE.GLTFLoader();

function loadFBXGirlAvatar(fbxUrl = '/static/models/GirlHologramRigged.fbx', texturesDir = '/static/models/Textures') {
    const statusEl = document.getElementById('status-indicator');
    if (statusEl) statusEl.textContent = 'Loading 3D Girl Model...';

    // 1. Load PBR Texture Maps (converted PNGs)
    const baseColor = textureLoader.load(`${texturesDir}/Witch_Witch_BaseColor.png`);
    baseColor.encoding = THREE.sRGBEncoding;
    const normalMap = textureLoader.load(`${texturesDir}/Witch_Witch_Normal.png`);
    const roughnessMap = textureLoader.load(`${texturesDir}/Witch_Witch_Roughness.png`);
    const metalnessMap = textureLoader.load(`${texturesDir}/Witch_Witch_Metalness.png`);

    customBaseMaterial = new THREE.MeshStandardMaterial({
        map: baseColor,
        normalMap: normalMap,
        roughnessMap: roughnessMap,
        metalnessMap: metalnessMap,
        roughness: 0.65,
        metalness: 0.15,
        skinning: true,
        envMap: envMap,
        envMapIntensity: 0.85
    });

    const loader = new THREE.FBXLoader();
    loader.load(
        fbxUrl,
        (fbx) => {
            if (loadedCustomAvatar) avatarRoot.remove(loadedCustomAvatar);
            loadedCustomAvatar = fbx;
            customMorphMeshes = [];
            customBones = {};

            // Auto-center and fit to camera view
            const bbox = new THREE.Box3().setFromObject(fbx);
            const size = bbox.getSize(new THREE.Vector3());
            const center = bbox.getCenter(new THREE.Vector3());

            // Target size framing (Bust / Torso portrait)
            const targetHeight = 2.4;
            const scale = (size.y > 0) ? (targetHeight / size.y) : 0.012;
            fbx.scale.set(scale, scale, scale);

            customModelBaseY = -center.y * scale - 0.25;
            fbx.position.set(-center.x * scale, customModelBaseY, -center.z * scale);

            fbx.traverse((child) => {
                if (child.isMesh || child.isSkinnedMesh) {
                    child.material = customBaseMaterial;
                    child.material.skinning = true;
                    child.castShadow = true;
                    child.receiveShadow = true;
                    if (child.morphTargetDictionary && child.morphTargetInfluences) {
                        customMorphMeshes.push(child);
                    }
                }

                // Identify all skeletal nodes & save initial rest rotation
                const name = (child.name || '').toLowerCase();
                const isBone = child.isBone || child.type === 'Bone' || name.includes('mixamo') || name.includes('arm') || name.includes('leg') || name.includes('spine') || name.includes('head') || name.includes('hip');

                if (isBone) {
                    child.userData.initRot = child.rotation.clone();

                    if (name.includes('hips') && !customBones.hips) customBones.hips = child;
                    if (name.includes('spine') && !name.includes('spine1') && !name.includes('spine2') && !customBones.spine) customBones.spine = child;
                    if ((name.includes('spine1') || name.includes('spine2') || name.includes('chest')) && !customBones.chest) customBones.chest = child;
                    if (name.includes('neck') && !customBones.neck) customBones.neck = child;
                    if (name.includes('head') && !name.includes('top') && !customBones.head) customBones.head = child;
                    if (name.includes('jaw') && !customBones.jaw) customBones.jaw = child;

                    // Arms & Hands
                    if (name.includes('leftshoulder') && !customBones.leftShoulder) customBones.leftShoulder = child;
                    if (name.includes('rightshoulder') && !customBones.rightShoulder) customBones.rightShoulder = child;
                    if (name.includes('leftarm') && !name.includes('forearm') && !customBones.leftArm) customBones.leftArm = child;
                    if (name.includes('rightarm') && !name.includes('forearm') && !customBones.rightArm) customBones.rightArm = child;
                    if (name.includes('leftforearm') && !customBones.leftForeArm) customBones.leftForeArm = child;
                    if (name.includes('rightforearm') && !customBones.rightForeArm) customBones.rightForeArm = child;
                    if (name.includes('lefthand') && !name.includes('thumb') && !name.includes('index') && !name.includes('middle') && !name.includes('ring') && !name.includes('pinky') && !customBones.leftHand) customBones.leftHand = child;
                    if (name.includes('righthand') && !name.includes('thumb') && !name.includes('index') && !name.includes('middle') && !name.includes('ring') && !name.includes('pinky') && !customBones.rightHand) customBones.rightHand = child;

                    // Legs & Feet
                    if (name.includes('leftupleg') && !customBones.leftUpLeg) customBones.leftUpLeg = child;
                    if (name.includes('rightupleg') && !customBones.rightUpLeg) customBones.rightUpLeg = child;
                    if (name.includes('leftleg') && !name.includes('up') && !customBones.leftLeg) customBones.leftLeg = child;
                    if (name.includes('rightleg') && !name.includes('up') && !customBones.rightLeg) customBones.rightLeg = child;
                    if (name.includes('leftfoot') && !customBones.leftFoot) customBones.leftFoot = child;
                    if (name.includes('rightfoot') && !customBones.rightFoot) customBones.rightFoot = child;
                }
            });

            // Initialize Three.js Animation Mixer for full Mocap Skeleton retargeting
            customAnimationMixer = new THREE.AnimationMixer(fbx);

            // Preload and start Idle Mocap loop
            loadMocapClip('idle', MOCAP_ANIMATION_MAP['idle'], (clip) => {
                idleMocapAction = customAnimationMixer.clipAction(clip);
                idleMocapAction.setLoop(THREE.LoopRepeat);
                idleMocapAction.play();
                currentMocapAction = idleMocapAction;
            });

            // Preload Talking Mocap clip
            loadMocapClip('talking', MOCAP_ANIMATION_MAP['talking']);

            // Setup finished event listener for one-shot dances & gestures
            customAnimationMixer.addEventListener('finished', (e) => {
                isMocapPlaying = false;
                if (idleMocapAction && currentMocapAction !== idleMocapAction) {
                    idleMocapAction.reset().fadeIn(0.4).play();
                    if (currentMocapAction) currentMocapAction.fadeOut(0.4);
                    currentMocapAction = idleMocapAction;
                }
                document.querySelectorAll('.gesture-pill-btn').forEach(btn => btn.classList.remove('active'));
            });

            customModelLoaded = true;
            avatarRoot.add(fbx);
            switchAvatarPreset('girl3d');
            if (statusEl) statusEl.textContent = 'Lisa • Ready';
        },
        (xhr) => {
            if (xhr.lengthComputable && statusEl) {
                const percent = Math.round((xhr.loaded / xhr.total) * 100);
                statusEl.textContent = `Loading 3D Girl Avatar (${percent}%)...`;
            }
        },
        (err) => {
            console.warn('Error loading FBX avatar:', err);
            if (statusEl) statusEl.textContent = 'Lisa • Ready';
        }
    );
}

function loadMocapClip(key, url, callback) {
    if (animationClips[key]) {
        if (callback) callback(animationClips[key]);
        return;
    }
    animFBXLoader.load(url, (animFbx) => {
        if (animFbx.animations && animFbx.animations.length > 0) {
            const rawClip = animFbx.animations[0];
            rawClip.name = key;
            rawClip.tracks.forEach(track => {
                track.name = track.name.replace(/mixamorig(\d*):/i, 'mixamorig:');
            });
            animationClips[key] = rawClip;
            if (customAnimationMixer) {
                const action = customAnimationMixer.clipAction(rawClip);
                animationActions[key] = action;
            }
            if (callback) callback(rawClip);
        }
    }, undefined, (err) => {
        console.warn(`Failed to load mocap animation '${key}' from ${url}:`, err);
    });
}

function playMocapAnimation(nameOrKey, loopMode = THREE.LoopOnce, crossFadeDuration = 0.45) {
    if (!customAnimationMixer || !loadedCustomAvatar) return false;
    
    const normalizedKey = (nameOrKey || '').toLowerCase().trim();
    let matchedKey = null;
    
    if (MOCAP_ANIMATION_MAP[normalizedKey]) {
        matchedKey = normalizedKey;
    } else {
        for (const k of Object.keys(MOCAP_ANIMATION_MAP)) {
            if (normalizedKey.includes(k) || k.includes(normalizedKey)) {
                matchedKey = k;
                break;
            }
        }
    }
    
    if (!matchedKey) {
        return false;
    }
    
    const url = MOCAP_ANIMATION_MAP[matchedKey];
    
    loadMocapClip(matchedKey, url, (clip) => {
        let action = animationActions[matchedKey];
        if (!action && customAnimationMixer) {
            action = customAnimationMixer.clipAction(clip);
            animationActions[matchedKey] = action;
        }
        if (!action) return;

        action.reset();
        action.setLoop(loopMode);
        if (loopMode === THREE.LoopOnce) {
            action.clampWhenFinished = true;
            isMocapPlaying = true;
        }
        action.fadeIn(crossFadeDuration);
        action.play();

        if (currentMocapAction && currentMocapAction !== action) {
            currentMocapAction.fadeOut(crossFadeDuration);
        }
        currentMocapAction = action;
    });
    
    return true;
}

function loadGLTFAvatar(url) {
    const statusEl = document.getElementById('status-indicator');
    if (statusEl) statusEl.textContent = 'Loading 3D Model...';

    gltfLoader.load(
        url,
        (gltf) => {
            if (loadedCustomAvatar) avatarRoot.remove(loadedCustomAvatar);
            loadedCustomAvatar = gltf.scene;
            customMorphMeshes = [];
            customBones = {};

            loadedCustomAvatar.traverse((node) => {
                if (node.isMesh) {
                    node.castShadow = true;
                    node.receiveShadow = true;
                    if (node.morphTargetDictionary && node.morphTargetInfluences) {
                        customMorphMeshes.push(node);
                    }
                }
                if (node.isBone) {
                    const name = node.name.toLowerCase();
                    if (name.includes('head')) customBones.head = node;
                    if (name.includes('neck')) customBones.neck = node;
                }
            });

            loadedCustomAvatar.position.set(0, -1.45, 0);
            avatarRoot.add(loadedCustomAvatar);
            customModelLoaded = true;
            switchAvatarPreset('girl3d');
            if (statusEl) statusEl.textContent = 'Lisa • Ready';
        },
        undefined,
        (err) => {
            console.warn('Error loading GLTF avatar:', err);
            if (statusEl) statusEl.textContent = 'Lisa • Ready';
        }
    );
}

// -------------------------------------------------------------
// 5. Lifelike Human Micro-Physics & 52-Blendshape Visemes
// -------------------------------------------------------------
const clock = new THREE.Clock();

function updateHumanoidPhysics(time) {
    // 1. Natural Sinusoidal Breathing Loop
    const breath = Math.sin(time * 1.5);
    const hoverY = breath * 0.014;

    // 2. Eye Saccades (Human Eye Darting)
    saccadeTimer += 0.016;
    if (saccadeTimer > 1.6 + Math.random() * 2.2) {
        saccadeTimer = 0;
        eyeSaccadeX = (Math.random() - 0.5) * 0.07;
        eyeSaccadeY = (Math.random() - 0.5) * 0.04;
    }

    // Smooth Gaze Interpolation
    currentGazeX += (targetGazeX + eyeSaccadeX - currentGazeX) * 0.07;
    currentGazeY += (targetGazeY + eyeSaccadeY - currentGazeY) * 0.07;

    // 3. Natural Randomized Micro-Blinking
    blinkTimer += 0.016;
    if (blinkTimer >= nextBlinkInterval) {
        isBlinking = true;
        blinkProgress += 0.24;
        if (blinkProgress >= 1.0) {
            isBlinking = false;
            blinkProgress = 0.0;
            blinkTimer = 0.0;
            nextBlinkInterval = 2.2 + Math.random() * 3.2;
        }
    }
    const blinkAmount = isBlinking ? Math.sin(blinkProgress * Math.PI) : 0.0;

    // 4. Speech Viseme & Audio Energy Calculation
    let jawOpen = 0.0;
    if (currentState === 'speaking') {
        const p1 = Math.sin(time * 16.0) * 0.45;
        const p2 = Math.cos(time * 24.0) * 0.25;
        const speechAmp = Math.max(audioEnergy, 0.42 + (p1 + p2) * 0.38);
        jawOpen = Math.max(0.04, speechAmp * 0.26);
    }

    // 6. Update Rigged 3D Custom Avatar (Mocap Animation Mixer, Gaze & Visemes)
    if (customAnimationMixer) {
        customAnimationMixer.update(0.016);
    }

    if (loadedCustomAvatar && loadedCustomAvatar.visible) {
        // Natural full-body breathing hover
        loadedCustomAvatar.position.y = customModelBaseY + hoverY * 0.7;

        // Apply additive head gaze tracking on top of mocap animation
        if (customBones.head) {
            customBones.head.rotation.y += currentGazeX * 0.25;
            customBones.head.rotation.x -= currentGazeY * 0.18;
        }
        if (customBones.neck) {
            customBones.neck.rotation.y += currentGazeX * 0.12;
            customBones.neck.rotation.x -= currentGazeY * 0.08;
        }

        // Jaw speech visemes
        if (customBones.jaw && customBones.jaw.userData.initRot) {
            const init = customBones.jaw.userData.initRot;
            customBones.jaw.rotation.x = init.x + jawOpen * 0.42;
        } else if (customBones.jaw) {
            customBones.jaw.rotation.x = jawOpen * 0.42;
        }

        if (customMorphMeshes.length > 0) {
            customMorphMeshes.forEach((mesh) => {
                const d = mesh.morphTargetDictionary;
                const inf = mesh.morphTargetInfluences;
                if (!d || !inf) return;

                if (d['jawOpen'] !== undefined) inf[d['jawOpen']] = jawOpen * 2.8;
                if (d['mouthOpen'] !== undefined) inf[d['mouthOpen']] = jawOpen * 2.5;
                if (d['viseme_aa'] !== undefined) inf[d['viseme_aa']] = jawOpen * 2.2;
                if (d['viseme_O'] !== undefined) inf[d['viseme_O']] = jawOpen * 1.8;
                if (d['eyeBlinkLeft'] !== undefined) inf[d['eyeBlinkLeft']] = blinkAmount;
                if (d['eyeBlinkRight'] !== undefined) inf[d['eyeBlinkRight']] = currentEmotion === 'playful' ? 0.9 : blinkAmount;
                if (d['mouthSmile'] !== undefined) inf[d['mouthSmile']] = (currentEmotion === 'affectionate' || currentEmotion === 'playful') ? 0.7 : 0.2;
            });
        }
    }
}

// -------------------------------------------------------------
// 6. Render Loop
// -------------------------------------------------------------
function animate() {
    requestAnimationFrame(animate);
    const time = clock.getElapsedTime();

    if (controls) controls.update();
    updateHumanoidPhysics(time);

    // 3D Holographic Environment Animations
    if (outerEnergyRing) outerEnergyRing.rotation.z = time * 0.25;
    if (innerEnergyRing) innerEnergyRing.rotation.z = -time * 0.42;
    if (overheadHalo) {
        overheadHalo.rotation.z = time * 0.14;
        overheadHalo.rotation.y = Math.sin(time * 0.3) * 0.15;
    }

    // Animate Quantum Starfield Drift
    if (starParticles && starParticles.geometry) {
        const positions = starParticles.geometry.attributes.position.array;
        for (let i = 0; i < starCount; i++) {
            positions[i * 3 + 1] += starSpeeds[i].y;
            positions[i * 3] = starSpeeds[i].baseX + Math.sin(time * starSpeeds[i].freq) * 0.12;
            if (positions[i * 3 + 1] > 6.5) {
                positions[i * 3 + 1] = -1.5;
            }
        }
        starParticles.geometry.attributes.position.needsUpdate = true;
    }

    // Orbiting Soft Rim Light
    rimLight.position.x = Math.sin(time * 0.32) * 3.2;
    rimLight.position.z = Math.cos(time * 0.32) * 3.2 - 1.2;

    renderer.render(scene, camera);
}

animate();

// -------------------------------------------------------------
// 7. Preset & Emotion Switchers
// -------------------------------------------------------------
// -------------------------------------------------------------
// 7. Preset & Emotion Switchers
// -------------------------------------------------------------
function switchAvatarPreset(preset) {
    currentPreset = preset;
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(preset));
    });

    if (preset === 'girl3d') {
        if (loadedCustomAvatar) {
            loadedCustomAvatar.visible = true;
            if (customBaseMaterial) {
                customBaseMaterial.color.setHex(0xffffff);
                customBaseMaterial.roughness = 0.65;
                customBaseMaterial.metalness = 0.15;
            }
        }
        scene.background.setHex(0x06080d);
        if (scene.fog) scene.fog.color.setHex(0x060812);
        keyLight.color.setHex(0xfff5ea);
        rimLight.color.setHex(0xff7096);
        updateEnvPalette(0x38bdf8, 0xf43f5e);
    } else if (preset === 'cyberpunk') {
        scene.background.setHex(0x04050a);
        if (scene.fog) scene.fog.color.setHex(0x04050a);
        if (loadedCustomAvatar && loadedCustomAvatar.visible) {
            if (customBaseMaterial) {
                customBaseMaterial.color.setHex(0xf0abfc);
                customBaseMaterial.roughness = 0.3;
                customBaseMaterial.metalness = 0.5;
            }
        }
        keyLight.color.setHex(0x38bdf8);
        rimLight.color.setHex(0xf43f5e);
        updateEnvPalette(0xf43f5e, 0x00f2fe);
    } else if (preset === 'hologram') {
        scene.background.setHex(0x020409);
        if (scene.fog) scene.fog.color.setHex(0x020409);
        if (loadedCustomAvatar && loadedCustomAvatar.visible) {
            if (customBaseMaterial) {
                customBaseMaterial.color.setHex(0x38bdf8);
                customBaseMaterial.roughness = 0.15;
                customBaseMaterial.metalness = 0.85;
            }
        }
        keyLight.color.setHex(0x00f2fe);
        rimLight.color.setHex(0x8b5cf6);
        updateEnvPalette(0x00f2fe, 0x8b5cf6);
    }
}

function updateEnvPalette(primaryHex, secondaryHex) {
    if (envRingMat) envRingMat.color.setHex(primaryHex);
    if (outerEnergyRingMat) outerEnergyRingMat.color.setHex(primaryHex);
    if (innerEnergyRingMat) innerEnergyRingMat.color.setHex(secondaryHex);
    if (conduitMat) conduitMat.color.setHex(primaryHex);
    if (haloMat) haloMat.color.setHex(primaryHex);
}

const EMOTION_AURAS = {
    affectionate: { color: 0xff4d88, rim: 0xff7096, env: 0xff7096 },
    playful: { color: 0xffb703, rim: 0xfb8500, env: 0xffb703 },
    caring: { color: 0x00f2fe, rim: 0x38bdf8, env: 0x38bdf8 },
    jealous: { color: 0xd90429, rim: 0xf43f5e, env: 0xf43f5e },
    tactical: { color: 0x3a86ff, rim: 0x60a5fa, env: 0x3a86ff }
};

function setEmotionState(emo) {
    if (!EMOTION_AURAS[emo]) return;
    currentEmotion = emo;
    const aura = EMOTION_AURAS[emo];
    rimLight.color.setHex(aura.rim);
    updateEnvPalette(aura.env, aura.rim);

    document.querySelectorAll('.emotion-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(emo));
    });
}

// -------------------------------------------------------------
// 8. Custom Gesture Trigger & Mocap Animation Engine
// -------------------------------------------------------------
function triggerCustomGesture(gestureName, durationMs = 3500) {
    const success = playMocapAnimation(gestureName, THREE.LoopOnce, 0.35);
    if (!success) {
        currentGesture = gestureName.toLowerCase();
        gestureStartTime = performance.now();
        gestureDuration = durationMs;
    }

    document.querySelectorAll('.gesture-pill-btn').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick')?.includes(gestureName));
    });
}

function setAvatarState(state, text = null, emotion = null, animation = null) {
    currentState = state.toLowerCase();
    const statusEl = document.getElementById('status-indicator');
    const responseEl = document.getElementById('response-text');

    if (statusEl) {
        statusEl.className = `status-indicator ${currentState}`;
        if (currentState === 'idle') statusEl.textContent = 'Lisa • Ready';
        else if (currentState === 'listening') statusEl.textContent = 'Lisa • Listening';
        else if (currentState === 'thinking') statusEl.textContent = 'Lisa • Thinking';
        else if (currentState === 'speaking') statusEl.textContent = 'Lisa • Speaking';
    }

    if (text && responseEl) {
        responseEl.textContent = text;
    }
    if (emotion && EMOTION_AURAS[emotion]) {
        setEmotionState(emotion);
    }

    // If explicit animation command was sent (from LLM [ANIMATION: ...] or UI)
    if (animation) {
        playMocapAnimation(animation, THREE.LoopOnce, 0.35);
        return;
    }

    // Automatic State based animation switching
    if (currentState === 'speaking' && !isMocapPlaying) {
        playMocapAnimation('talking', THREE.LoopRepeat, 0.35);
    } else if (currentState === 'idle' && !isMocapPlaying) {
        if (idleMocapAction && currentMocapAction !== idleMocapAction) {
            idleMocapAction.reset().fadeIn(0.4).play();
            if (currentMocapAction) currentMocapAction.fadeOut(0.4);
            currentMocapAction = idleMocapAction;
        }
    }
}

// -------------------------------------------------------------
// 9. Mouse & Gaze Tracking
// -------------------------------------------------------------
window.addEventListener('mousemove', (e) => {
    targetGazeX = ((e.clientX / window.innerWidth) - 0.5) * 1.15;
    targetGazeY = -((e.clientY / window.innerHeight) - 0.5) * 0.85;
});

// -------------------------------------------------------------
// 10. WebSocket Real-Time Bridge
// -------------------------------------------------------------
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'state_change') {
                setAvatarState(data.state, data.text, data.emotion, data.animation || data.gesture);
                if (data.energy) audioEnergy = data.energy;
            } else if (data.type === 'inner_monologue') {
                displayInnerThought(data.thought, data.gesture, data.emotion);
            } else if (data.type === 'animation') {
                playMocapAnimation(data.animation, THREE.LoopOnce, 0.35);
            } else if (data.type === 'gesture') {
                triggerCustomGesture(data.gesture, data.duration || 3500);
            } else if (data.type === 'audio_energy') {
                audioEnergy = data.energy || 0.0;
            } else if (data.type === 'face_tracking_update' && data.box) {
                targetGazeX = ((data.box.x + data.box.w / 2) / (data.box.frame_w || 640) - 0.5) * 1.3;
                targetGazeY = -((data.box.y + data.box.h / 2) / (data.box.frame_h || 480) - 0.5) * 1.0;
            }
        } catch (e) {}
    };

    socket.onclose = () => {
        setTimeout(connectWebSocket, 2000);
    };
}

function displayInnerThought(thought, gesture, emotion) {
    const pill = document.getElementById('inner-thought-pill');
    const textEl = document.getElementById('thought-text');
    if (textEl && thought) {
        textEl.textContent = thought;
    }
    if (pill) {
        pill.classList.add('pulse');
        setTimeout(() => pill.classList.remove('pulse'), 3000);
    }
    if (gesture && !isMocapPlaying) {
        playMocapAnimation(gesture, THREE.LoopOnce, 0.4);
    }
    if (emotion && EMOTION_AURAS[emotion]) {
        setEmotionState(emotion);
    }
}

connectWebSocket();

// -------------------------------------------------------------
// 10. Chat Transmitter & Browser Mic
// -------------------------------------------------------------
async function handleChatSubmit(e) {
    e.preventDefault();
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    input.value = '';
    setAvatarState('thinking', `"${message}"`);

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message })
        });
        const data = await res.json();
        setAvatarState('speaking', data.response);

        const readDuration = Math.max(3500, data.response.length * 55);
        setTimeout(() => {
            if (currentState === 'speaking') {
                setAvatarState('idle', data.response);
            }
        }, readDuration);

    } catch (err) {
        setAvatarState('idle', 'Could not reach Lisa.');
    }
}

let recognition = null;
let isRecording = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
        isRecording = true;
        const micBtn = document.getElementById('mic-btn');
        if (micBtn) micBtn.classList.add('recording');
        setAvatarState('listening', 'Listening to your voice...');
    };

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById('chat-input');
        if (input) input.value = transcript;
        handleChatSubmit({ preventDefault: () => {} });
    };

    recognition.onerror = () => {
        isRecording = false;
        const micBtn = document.getElementById('mic-btn');
        if (micBtn) micBtn.classList.remove('recording');
        setAvatarState('idle');
    };

    recognition.onend = () => {
        isRecording = false;
        const micBtn = document.getElementById('mic-btn');
        if (micBtn) micBtn.classList.remove('recording');
    };
}

function toggleVoiceRecording() {
    if (!recognition) {
        alert("Speech Recognition not supported in this browser. Please use Chrome or Edge.");
        return;
    }
    if (isRecording) {
        recognition.stop();
    } else {
        try { recognition.start(); } catch (e) { recognition.stop(); }
    }
}



window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

// Auto-load the 3D Rigged Girl Avatar on Startup
loadFBXGirlAvatar('/static/models/GirlHologramRigged.fbx', '/static/models/Textures');
