const satori = require('satori').default;
const { html } = require('satori-html');
const fs = require('fs');
const path = require('path');

async function main() {
    const inputHtml = process.argv[2];
    if (!inputHtml) {
        console.error("Missing HTML input");
        process.exit(1);
    }

    // Hardcoded font for now
    const fontPath = 'C:\\Users\\Abid\\AppData\\Roaming\\Claude\\local-agent-mode-sessions\\skills-plugin\\44662c0e-9dd9-4ef7-9fb6-babec25545e9\\827e3b85-698e-4c7d-ac00-e815d3d1f106\\skills\\canvas-design\\canvas-fonts\\WorkSans-Regular.ttf';
    const fontData = fs.readFileSync(fontPath);

    const markup = html(inputHtml);
    const svg = await satori(markup, {
        width: 1200,
        height: 630,
        fonts: [
            {
                name: 'WorkSans',
                data: fontData,
                weight: 400,
                style: 'normal',
            },
        ],
    });

    process.stdout.write(svg);
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
