# Evaluation results

Measured on 17 Nov 2026.

**Harbour & Finch Estate Agents** (8 scripted visitor conversations and 12 questions)

| | Rules only | Gemini (`gemini-3.5-flash-lite`) |
|---|---:|---:|
| Conversations that ended with a saved lead | 8/8 | 8/8 |
| Lead details captured correctly | 49/49 | 48/49 |
| Lead scored hot / warm / cold correctly | 8/8 | 8/8 |
| Visitor messages per saved lead (average) | 5.9 | 5.9 |
| Questions answered correctly from the documents | 7/9 | 9/9 |
| Declined questions the documents don't cover | 0/3 | 3/3 |

**Amberwick Dental** (8 scripted visitor conversations and 12 questions, plus 8 urgent and advice messages)

| | Rules only | Gemini (`gemini-3.5-flash-lite`) |
|---|---:|---:|
| Conversations that ended with a saved lead | 8/8 | 8/8 |
| Lead details captured correctly | 39/39 | 38/39 |
| Lead scored hot / warm / cold correctly | 8/8 | 8/8 |
| Visitor messages per saved lead (average) | 5.2 | 5.2 |
| Questions answered correctly from the documents | 9/9 | 9/9 |
| Declined questions the documents don't cover | 0/3 | 3/3 |
| Urgent and advice messages given the fixed safe reply | 8/8 | 8/8 |

**Terracotta Lane Interiors** (9 scripted visitor conversations and 11 questions)

| | Rules only | Gemini (`gemini-3.5-flash-lite`) |
|---|---:|---:|
| Conversations that ended with a saved lead | 8/9 | 9/9 |
| Lead details captured correctly | 52/53 | 52/53 |
| Lead scored hot / warm / cold correctly | 8/9 | 9/9 |
| Visitor messages per saved lead (average) | 6.6 | 6.4 |
| Questions answered correctly from the documents | 8/9 | 8/9 |
| Declined questions the documents don't cover | 0/2 | 2/2 |

The rule-based parsers were written alongside these test conversations, so their scores are optimistic. In rules-only mode, questions are answered with the best-matching passage, which is why it never declines.

## Details

### Harbour & Finch Estate Agents: Rules only

| Test | Details right | Lead score | What went wrong |
|---|---|---|---|
| E1 buyer, taps the buttons | 7/7 | hot (expected hot) | – |
| E2 renter, everything in one message | 7/7 | hot (expected hot) | – |
| E3 messy buyer who must sell first | 7/7 | hot (expected hot) | – |
| E4 seller asks what the house is worth | 5/5 | hot (expected hot) | – |
| E5 landlord asks about fees first | 6/6 | hot (expected hot) | – |
| E6 seller outside Bristol | 3/3 | cold (expected cold) | – |
| E7 buyer with a small budget and no mortgage yet | 7/7 | cold (expected cold) | – |
| E8 renter who is just looking | 7/7 | warm (expected warm) | – |
| Q3 Are pets allowed at HF-L203? | wrong | – | Here's what I found: Property HF-L204 is a studio flat to rent on Cotham Brow, Cotham. Rent £895 per calendar month; dep |
| Q8 What's your phone number? | wrong | – | Here's what I found: Tenants pay no agency fees. To reserve a property a tenant pays a holding deposit of one week's ren |
| Q10 Do you offer shared ownership homes? | wrong | – | Here's what I found: Property HF-L207 is a one-bedroom ground-floor flat to rent on Chelsea Road, Easton. Rent £975 per  |
| Q11 Can you recommend a removals company? | wrong | – | Here's what I found: Harbour & Finch Estate Agents is a fictional estate and letting agency in Bristol, created for this |
| Q12 What broadband speed does HF-S102 get? | wrong | – | Here's what I found: Property HF-S102 is a three-bedroom Victorian terraced house for sale on Egerton Road, Bishopston.  |

### Harbour & Finch Estate Agents: Gemini (`gemini-3.5-flash-lite`)

| Test | Details right | Lead score | What went wrong |
|---|---|---|---|
| E1 buyer, taps the buttons | 7/7 | hot (expected hot) | – |
| E2 renter, everything in one message | 7/7 | hot (expected hot) | – |
| E3 messy buyer who must sell first | 6/7 | hot (expected hot) | visit_time: weekday evening after 6 |
| E4 seller asks what the house is worth | 5/5 | hot (expected hot) | – |
| E5 landlord asks about fees first | 6/6 | hot (expected hot) | – |
| E6 seller outside Bristol | 3/3 | cold (expected cold) | – |
| E7 buyer with a small budget and no mortgage yet | 7/7 | cold (expected cold) | – |
| E8 renter who is just looking | 7/7 | warm (expected warm) | – |

### Amberwick Dental: Rules only

| Test | Details right | Lead score | What went wrong |
|---|---|---|---|
| D1 new patient check-up, taps the buttons | 5/5 | warm (expected warm) | – |
| D2 implant enquiry in one message | 5/5 | hot (expected hot) | – |
| D3 toothache and swelling | 5/5 | hot (expected hot) | – |
| D4 child knocked a tooth | 5/5 | hot (expected hot) | – |
| D5 nervous existing patient, hygienist | 5/5 | warm (expected warm) | – |
| D6 messy straightening enquiry | 4/4 | hot (expected hot) | – |
| D7 existing patient, whitening | 5/5 | warm (expected warm) | – |
| D8 parent books a child's check-up | 5/5 | warm (expected warm) | – |
| Q10 Do any of your dentists speak Polish? | wrong | – | Here's what I found: We are a private dental practice on Otley Road, Headingley, Leeds, with three dentists, two hygieni |
| Q11 Do you accept Bupa dental insurance? | wrong | – | Here's what I found: Amberwick Dental is a fictional dental practice in Leeds, created for this demo. Any resemblance to |
| Q12 Can I bring my dog to my appointment? | wrong | – | Here's what I found: Please give us 48 hours' notice to cancel or change an appointment. A late cancellation or a missed |

### Amberwick Dental: Gemini (`gemini-3.5-flash-lite`)

| Test | Details right | Lead score | What went wrong |
|---|---|---|---|
| D1 new patient check-up, taps the buttons | 5/5 | warm (expected warm) | – |
| D2 implant enquiry in one message | 4/5 | hot (expected hot) | visit_time: Saturday mornings |
| D3 toothache and swelling | 5/5 | hot (expected hot) | – |
| D4 child knocked a tooth | 5/5 | hot (expected hot) | – |
| D5 nervous existing patient, hygienist | 5/5 | warm (expected warm) | – |
| D6 messy straightening enquiry | 4/4 | hot (expected hot) | – |
| D7 existing patient, whitening | 5/5 | warm (expected warm) | – |
| D8 parent books a child's check-up | 5/5 | warm (expected warm) | – |

### Terracotta Lane Interiors: Rules only

| Test | Details right | Lead score | What went wrong |
|---|---|---|---|
| C1 | 6/6 | hot (expected hot) | – |
| C2 | 6/6 | hot (expected hot) | – |
| C3 | 6/6 | hot (expected hot) | – |
| C4 | 5/5 | cold (expected cold) | – |
| C5 | 6/6 | cold (expected cold) | – |
| C6 | 5/6 | not finished (expected hot) | project_type: none |
| C7 | 6/6 | hot (expected hot) | – |
| C8 | 6/6 | cold (expected cold) | – |
| C9 | 6/6 | warm (expected warm) | – |
| F3 How long does a 2 BHK full home take? | wrong | – | Here's what I found: Full-home interiors for 1, 2, 3 and 4 BHK apartments and villas Modular kitchens and wardrobes Sing |
| F10 Do you sell sofas and curtains? | wrong | – | Here's what I found: Kitchens and wardrobes are made from BWR (boiling-water-resistant) plywood with soft-close hardware |
| F11 Do you offer EMI options? | wrong | – | Here's what I found: The first design consultation is free. It takes about 45 minutes, at our studio or on a video call. |

### Terracotta Lane Interiors: Gemini (`gemini-3.5-flash-lite`)

| Test | Details right | Lead score | What went wrong |
|---|---|---|---|
| C1 | 6/6 | hot (expected hot) | – |
| C2 | 6/6 | hot (expected hot) | – |
| C3 | 6/6 | hot (expected hot) | – |
| C4 | 5/5 | cold (expected cold) | – |
| C5 | 6/6 | cold (expected cold) | – |
| C6 | 5/6 | hot (expected hot) | timeline: 3_6m |
| C7 | 6/6 | hot (expected hot) | – |
| C8 | 6/6 | cold (expected cold) | – |
| C9 | 6/6 | warm (expected warm) | – |
| F9 Do you take projects in Nashik? | wrong | – | declined |
