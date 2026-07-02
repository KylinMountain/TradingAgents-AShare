const { execSync } = require('child_process');

try {
  const output = execSync('netstat -ano', { encoding: 'utf8' });
  const lines = output.split('\n');
  const target = lines.find(l => l.includes(':5173') && l.includes('LISTENING'));
  if (target) {
    const pid = target.trim().split(/\s+/).pop();
    console.log(`Killing process ${pid} on port 5173...`);
    execSync(`taskkill /F /PID ${pid} /T`, { stdio: 'ignore' });
    console.log('Done');
  }
} catch (e) {
  // Ignore errors - port might not be in use
}
