// Utility function to convert email to deterministic UUID
export async function emailToUUID(email: string): Promise<string> {
    // Use Web Crypto API to create a consistent hash
    const encoder = new TextEncoder();
    const data = encoder.encode(email.toLowerCase().trim());
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));

    // Convert to hex string
    const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

    // Format as UUID (8-4-4-4-12)
    return [
        hashHex.substring(0, 8),
        hashHex.substring(8, 12),
        '4' + hashHex.substring(13, 16), // Version 4 UUID
        ((parseInt(hashHex.substring(16, 17), 16) & 0x3) | 0x8).toString(16) + hashHex.substring(17, 20), // Variant bits
        hashHex.substring(20, 32)
    ].join('-');
}