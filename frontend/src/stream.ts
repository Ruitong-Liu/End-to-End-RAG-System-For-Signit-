export async function readEvents(response: Response, onEvent: (event: string, data: any) => void) {
  if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`);
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let lineBuffer = '', event = 'message', dataLines: string[] = [];
  function line(value: string) {
    if (value === '') {
      if (dataLines.length) onEvent(event, JSON.parse(dataLines.join('\n')));
      event = 'message'; dataLines = []; return;
    }
    if (value.startsWith(':')) return;
    const colon = value.indexOf(':');
    const field = colon < 0 ? value : value.slice(0, colon);
    let valueText = colon < 0 ? '' : value.slice(colon + 1);
    if (valueText.startsWith(' ')) valueText = valueText.slice(1);
    if (field === 'event') event = valueText;
    if (field === 'data') dataLines.push(valueText);
  }
  try {
    while (true) {
      const {done, value} = await reader.read();
      lineBuffer += decoder.decode(value, {stream: !done});
      let boundary: number;
      while ((boundary = lineBuffer.indexOf('\n')) >= 0) {
        line(lineBuffer.slice(0, boundary).replace(/\r$/, ''));
        lineBuffer = lineBuffer.slice(boundary + 1);
      }
      if (done) {
        if (lineBuffer.trim() || dataLines.length) throw new Error('The response ended unexpectedly.');
        break;
      }
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
