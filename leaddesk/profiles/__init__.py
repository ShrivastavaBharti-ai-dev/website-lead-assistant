"""Business profiles. One module per business; the engine (conversation,
extract, service) contains nothing about any particular business.

A profile module must define:

    KEY, BUSINESS, DOCS                      url-safe id, display name, folder of the business's documents
    GREETING, GREETING_CHOICES               first message and its buttons
    OFFER, OFFER_CHOICES, OFFER_TRIGGER      the offer to take details, and the question pattern that prompts it
    NOT_FOUND, HELP, AFTER_SUBMIT, CHAT_END  fixed replies
    WANTS                                    pattern meaning "start taking my details"
    QUESTIONS, REQUIRED                      field -> (question, buttons), and the order to ask in
    rule_fields(message, asked)              details found by plain rules
    normalise_fields(raw), parse_phone(text) validation, also applied to the AI's output
    EXTRACT_SCHEMA, EXTRACT_PROMPT           the AI extractor's output shape and instructions
    qualify(lead) -> Qualification           hot / warm / cold with reasons
    LEAD_HEADER, lead_columns(lead)          this business's sheet columns
    hot_lead_alert(lead, why), thanks(lead, result)
"""
