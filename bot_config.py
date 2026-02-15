# Bot Configuration

# Role Bot
ENABLE_ROLE_BOT = True
ROLE_BOT_NICKNAME = "Sudo Master"
ROLE_BOT_FOOTER = "Obtain your roles!"
AUTO_JOIN_ROLE_ID = 0 # Replace with actual Role ID to give on join

# Welcome Bot
ENABLE_WELCOME_BOT = True
WELCOME_BOT_NICKNAME = "Jeff the Doorman"

# Event Bot
ENABLE_EVENT_BOT = True
EVENT_BOT_NICKNAME = "The Event Loop"
EVENT_BOT_FOOTER = "Notifying you of upcoming events!"

# Stream Bot
ENABLE_STREAM_BOT = True
STREAM_BOT_NICKNAME = "The G-Code Guardian"

# Welcome Puns
WELCOME_PUNS = [
    # --- Electrical Engineering ---
    "Welcome! We hope you have the *potential* to be great here!",
    "Ohm my god, a new member!",
    "We're *currently* very excited to meet you!",
    "You act like a sine wave, you're always around!",
    "Don't be *resistant* to saying hello!",
    "We've been *waiting* for you with high frequency!",
    "Watt is up? Welcome to the team!",
    "You’ve got such a positive *charge*!",
    "Let’s help you get *plugged* into the workflow.",
    "We have high *capacitance* for new talent.",
    "No need to be *static*, feel free to move around!",
    "You’re really *conducting* yourself well so far.",
    "We’re shocked—*positively*—to have you here!",
    "Keep that *spark* alive!",
    "You’ve really *brightened* up the circuit.",

    # --- Mechanical Engineering ---
    "We are *geared* up to meet you!",
    "It is *riveting* to have you here!",
    "We hope you *weld* well with the team!",
    "Let's *torque* about your projects!",
    "You make our team run like a well-oiled machine!",
    "We're under a lot of *pressure* to make a good impression!",
    "You’ve really shifted our *momentum* forward.",
    "We promise not to *grind* your gears too much.",
    "You’re the *crank* that keeps us turning!",
    "Let’s not have any *friction* between us.",
    "We have high *tolerances* for fun here.",
    "You’re a real *bolt* of energy!",
    "Let’s keep this *engine* purring.",
    "You’ve got some serious *leverage* now.",
    "We’re *pumping* with excitement!",

    # --- Civil & Structural Engineering ---
    "You’re the *foundation* of our future success!",
    "We’ve built up a lot of excitement for your arrival.",
    "Let’s *bridge* the gap between our teams.",
    "You really *support* the structure of this group.",
    "Concrete evidence suggests you’re going to be great!",
    "We’re *beaming* with pride to have you.",
    "Don't worry, we won’t *truss* you with too much at once.",
    "You’ve got a *solid* reputation!",
    "Let's lay the *groundwork* for a great career.",
    "You’re a *pillar* of the community already.",
    "We’re *paving* the way for your success.",
    "Don't *arch* your eyebrows at our jokes!",
    "You really *cement* the team together.",
    "We’ve reached a new *level* with you here.",
    "You’ve got great *frames* of reference.",

    # --- Chemical Engineering ---
    "We have great *chemistry* already!",
    "You’re the *catalyst* for our next big project.",
    "Let’s keep the *solutions* flowing.",
    "We hope you find this environment *reactive*!",
    "You’re a *mole*-cool person to work with.",
    "Don't be a *base*, be a leader!",
    "We’ve reached a state of *equilibrium* now that you're here.",
    "You’ve got the right *formula* for success.",
    "Let’s see what we can *distill* from this meeting.",
    "You’re *solid*, *liquid*, and *gas*—all in one!",
    "We promise not to push you to your *boiling point*.",
    "You’re a *rare element* in this industry.",
    "Stay *concentrated* on your goals!",
    "We’re *bonding* already, aren't we?",
    "That was a *precipitate* entrance!",

    # --- Software & Computer Engineering ---
    "Welcome to the *array* of talent!",
    "We hope you *byte* off just enough to chew.",
    "You’re just our *type*!",
    "Let’s *git* to work!",
    "We’ve been *searching* for someone like you.",
    "You’ve got a *logical* approach to things.",
    "No *bugs* allowed in this welcome party!",
    "You’re the *key* to our next *string* of successes.",
    "We’re *streaming* with joy!",
    "You’ve really *crashed* through our expectations.",
    "Let’s *interface* soon!",
    "You’ve got a *cache* of great ideas.",
    "Welcome to the *cloud* nine of teams!",
    "We’ve *compiled* a list of reasons why you’re great.",
    "You’ve got a *bit* of everything we need.",

    # --- Aerospace & Aeronautical Engineering ---
    "Your career is ready for *takeoff*!",
    "You’re really *elevating* the team.",
    "The sky is the limit, but for you, it’s just the *floor*.",
    "We’re *over the moon* to have you!",
    "You’ve got a high *thrust*-to-weight ratio.",
    "Don't let the work *drag* you down.",
    "You’re a real *pilot* of innovation.",
    "We’re *orbiting* around your greatness.",
    "You’ve got a *stellar* attitude!",
    "Keep your *head in the clouds*—that’s where the ideas are.",
    "You’re *Mach*ing great time on your training.",
    "Let’s *launch* this project together!",
    "You’ve got the *right stuff*.",
    "We’re in a *stable flight* pattern now.",
    "You’ve really *soared* past the competition.",

    # --- Biomedical Engineering ---
    "You’re the *heart* of this operation!",
    "You’ve got *DNA*-level talent.",
    "We’re *jointly* excited to work with you.",
    "You’ve got a *pulse* on the industry.",
    "Let’s get under the *microscope* and look at your goals.",
    "You’re a *breath* of fresh air.",
    "We’ve *transplanted* you into the perfect team.",
    "You’re *cell*-ebrating a new beginning!",
    "You’ve got *backbone*!",
    "Let's see what *develops* in the lab.",
    "You’re *vital* to our success.",
    "We’re *nerve*-ous... just kidding, we're thrilled!",
    "You’re a *brainy* addition to the group.",
    "You’ve got great *vessels* for ideas.",
    "We’re *pumped* to see your progress!",

    # --- Industrial & Systems Engineering ---
    "We’re *optimizing* our team with you!",
    "You’ve improved our *efficiency* already.",
    "You’re at the top of our *supply chain*.",
    "Let’s *process* this welcome together.",
    "You’re a *standard* of excellence.",
    "We’ve *streamlined* our excitement just for you.",
    "You’re the missing *link* in our system.",
    "Let’s *model* some great behavior.",
    "You’ve got a *lean* and mean work ethic!",
    "We’re *queueing* up to meet you.",
    "You’ve really *integrated* well.",
    "Your *output* is already impressive.",
    "We’ve reached a *peak* with your arrival.",
    "You’re a *quality* hire!",
    "Let’s minimize the *waste* and maximize the fun.",

    # --- Environmental & Nuclear Engineering ---
    "You’re a *natural resource* for this team.",
    "We’re *glowing* with excitement!",
    "You’ve got a *fission* for success.",
    "Let’s keep the environment *sustainable*.",
    "You’re a *radiant* addition to the office.",
    "We’ve reached a *critical mass* of talent.",
    "You’re a *breath* of green air.",
    "Let’s *react* positively to this new start.",
    "You’ve got *core* strengths we admire.",
    "We’re *filtering* out the bad vibes.",
    "You’re a *powerful* new member.",
    "Keep that *energy* clean!",
    "You’ve got an *atomic* personality.",
    "We’re *enriched* by your presence.",
    "You’re the *power plant* of the office!"
]