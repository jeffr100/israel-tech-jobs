// Site settings. Edit this file to switch on email sign-up and Google AdSense ads.
// Nothing here is secret: it is read by visitors' browsers.
window.SITE_CONFIG = {
  // ---- Email updates (Brevo) ------------------------------------------------
  // In Brevo, make three contact lists (daily, weekly, monthly) and one sign-up form for each
  // list (Contacts > Forms > Create a subscription form; send to that list). For each form,
  // open Share > "HTML code" and copy the form's action address, which looks like
  //   https://xxxxxxxx.sibforms.com/serve/MUIFA...
  // and paste it below. Visitors' choice of daily / weekly / monthly picks the form.
  newsletter: {
    provider: "brevo",           // "brevo", "buttondown" or "custom"
    brevoForms: {
      daily:   "https://8361b465.sibforms.com/serve/MUIFABmgaGDTOOQNZvp2eoIJ1tA1QfaNUxPdMF13tIYt5jYKA6hTbVPSpzAPFa3JCCKBrARyNlSI3ecf2mAJPdLWIMMN9OXl2ayghuUlwAkPKjU4d6XSpOLhKRj_sTiMbMp3qXJ5Fpxq54DD0T2CrnVGIezPVox30kD5sL9c5URzZlwMBkKbKaLGfOUatx67SEjOlTBrgqcgCImcTA",
      weekly:  "https://8361b465.sibforms.com/serve/MUIFAInRD5NhQ7VROVy_Oyjirq_6Z6j01OQKVxxHURBeOSjmDxQTAYe0sq4qW7IKkudQBzEee2ANrij_c8i9on7nWlfzVZ9d2p-aUDCEyZlgdP1HmHzXiycFbVCZiMlpQrbMlj6LXcm5FCuRn5djsuTIITKLT8kNCQApGzU7z3QZlczD3vZu4jZXIs66xbVn3cF76WUAs_4hNO7kSQ",
      monthly: "https://8361b465.sibforms.com/serve/MUIFABFUG3TMwe5DFPGbr8Tlv2P_SVzFYCsBhXQJZ2eSoOqB4GGSgnpQdCbtz6B9GrXyhLS4lXebeB3F0d6WGSSSdS6L6bNFct9gRlcK5Qawd1Trn4SINKJ7xIekezjgua6OnxAmeBmSBxeA-9PAGNnMWVK8r2Ze9-YyH6CfGf8sLS6mF0coDfaAKwEkKAGZmu2qYHWS9UMzYdj25g"
    },
    // Buttondown instead: provider "buttondown" and your username here
    username: "",
    // Another service: provider "custom", its form address and field names
    action: "",
    emailField: "email",
    frequencyField: "tag"
  },

  // ---- Google AdSense: small text ads ---------------------------------------
  // Google no longer offers "text only" display units. Small text ads now come from
  // native In-feed ad units styled with the "Text only" template. In AdSense:
  //   Ads > By ad unit > In-feed ads > "Manual" style > template "Text only"
  // Create one unit per spot below and copy its data-ad-slot and data-ad-layout-key here.
  // After approval, paste your publisher ID ("ca-pub-…") and copy ads.txt.example to ads.txt.
  adsense: {
    client: "",                  // e.g. "ca-pub-1234567890123456"
    slots: {
      top:  { slot: "", layoutKey: "" },   // 3rd item in the job list
      feed: { slot: "", layoutKey: "" },   // repeats inside the job list
      side: { slot: "", layoutKey: "" }    // under the sign-up box in the sidebar (desktop)
    },
    feedEvery: 25,               // a text ad after every N jobs
    showPlaceholders: false,     // while client is blank, show outlines where the ads will go
    disableOnGithubPages: true   // no ads (or outlines) when the site is served from *.github.io
  }
};
