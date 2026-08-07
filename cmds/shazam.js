const fs = require("fs");
const path = require("path");
const axios = require("axios");

// URL de ton API Shazam déployée sur Render
const API_URL = "https://shazam-api.onrender.com";

module.exports = {
  config: {
    name: "shazam",
    aliases: ["whatmusic", "song"],
    author: "Kay",
    version: "1.0",
    cooldowns: 5,
    role: 0,
    shortDescription: "Reconnaître un son (audio/vidéo)",
    longDescription: "Réponds à un audio ou une vidéo avec cette commande pour obtenir le titre et l'artiste du son.",
    category: "media",
    guide: "Réponds à un audio/vidéo avec {pn}  |  {pn} <lien audio/vidéo>"
  },

  onStart: async function ({ message, args, api, event }) {
    const reply = event.messageReply?.attachments?.[0];
    const mediaUrl =
      (reply && ["audio", "video", "voice_clip", "video_inline"].includes(reply.type) ? reply.url : null) ||
      (args[0]?.startsWith("http") ? args[0] : null);

    if (!mediaUrl) {
      return message.reply("🎵 | Réponds à un audio ou une vidéo (ou donne un lien) pour identifier le son.");
    }

    api.setMessageReaction("🎧", event.messageID, () => {}, true);

    try {
      const res = await axios.post(
        `${API_URL}/recognize?text=1`,
        { url: mediaUrl },
        { timeout: 180000 }
      );

      const data = res.data;
      if (!data?.success || !data.result) {
        api.setMessageReaction("❌", event.messageID, () => {}, true);
        return message.reply(`❌ | ${data?.error || "Son non reconnu."}`);
      }

      api.setMessageReaction("✅", event.messageID, () => {}, true);

      const body = `🎶✨ | Son identifié !\n\n${data.text}`;

      if (data.result.cover) {
        try {
          const cacheFolder = path.join(__dirname, "/tmp");
          if (!fs.existsSync(cacheFolder)) fs.mkdirSync(cacheFolder);
          const imgRes = await axios.get(data.result.cover, { responseType: "arraybuffer", timeout: 60000 });
          const imgPath = path.join(cacheFolder, `shazam_${Date.now()}.jpg`);
          fs.writeFileSync(imgPath, imgRes.data);
          return message.reply({ body, attachment: fs.createReadStream(imgPath) });
        } catch (_) {
          // pochette indisponible : on envoie juste le texte
        }
      }

      return message.reply(body);
    } catch (error) {
      api.setMessageReaction("❌", event.messageID, () => {}, true);
      console.error("Shazam error:", error?.response?.data || error.message);
      const apiError = error?.response?.data?.error;
      message.reply(`❌ | Échec : ${apiError || error.message}`);
    }
  }
};
