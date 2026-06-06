const satori = require('satori').default;
const { html } = require('satori-html');
const fs = require('fs');
const path = require('path');

function findFont() {
    const searchPaths = [
        process.env.FONT_PATH,
        'WorkSans-Regular.ttf',
        path.join(__dirname, 'fonts', 'WorkSans-Regular.ttf'),
        path.join(__dirname, '..', '..', 'fonts', 'WorkSans-Regular.ttf'),
        '/app/fonts/WorkSans-Regular.ttf',
        '/usr/share/fonts/truetype/WorkSans-Regular.ttf',
    ].filter(Boolean);

    for (const fp of searchPaths) {
        try {
            if (fs.existsSync(fp)) return fp;
        } catch { }
    }
    console.error("Font not found. Set FONT_PATH env var or place WorkSans-Regular.ttf in ./fonts/");
    process.exit(1);
}

async function main() {
    const inputHtml = process.argv[2];
    if (!inputHtml) {
        console.error("Missing HTML input");
        process.exit(1);
    }

    const fontPath = findFont();
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
