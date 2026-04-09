process.chdir(__dirname);
const port = process.env.PORT || 3000;
require('child_process').execSync(`node node_modules/vite/bin/vite.js --port ${port} --host`, { stdio: 'inherit' });
