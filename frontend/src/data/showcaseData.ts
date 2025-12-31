/**
 * Showcase Content Data
 * Sample data for Singularities, Lostbelts, and Servant columns
 */
import type { ShowcaseContent } from '../components/showcase'

// Singularity Data
export const singularities: ShowcaseContent[] = [
  {
    id: 'singularity-f',
    type: 'singularity',
    title: 'Fuyuki',
    subtitle: 'Flame Contaminated City',
    chapter: 'Singularity F',
    era: 'Modern Era',
    year: 2004,
    location: 'Fuyuki, Japan',
    description: 'The prologue singularity where the story begins. A Holy Grail War that should have ended in 2004 continues indefinitely, with the city engulfed in flames. This is where the protagonist first encounters Mash Kyrielight and begins their journey as a Master.',
    sections: [
      {
        title: 'Synopsis',
        content: 'Fuyuki City has been transformed into a burning hellscape where the Holy Grail War never ended. Corrupted Servants roam the streets, and the Grail itself has become a source of destruction. The newly awakened Master must work with the Demi-Servant Mash to investigate and correct this anomaly.'
      }
    ],
    historicalBasis: 'Based on the Fourth and Fifth Holy Grail Wars from the Fate/stay night and Fate/Zero timelines. The concept of a corrupted Grail War draws from the original visual novel\'s lore about the Angra Mainyu corruption.',
    relatedServants: [
      { name: 'Mash Kyrielight', class: 'Shielder', rarity: 3 },
      { name: 'Caster (Cu Chulainn)', class: 'Caster', rarity: 3 },
      { name: 'Saber Alter', class: 'Saber', rarity: 4 }
    ],
    sources: ['Fate/Grand Order', 'Fate/stay night', 'Fate/Zero']
  },
  {
    id: 'singularity-1',
    type: 'singularity',
    title: 'Orleans',
    subtitle: 'Hundred Years\' War of the Evil Dragons',
    chapter: 'First Singularity',
    era: 'Medieval',
    year: 1431,
    location: 'France',
    description: 'The year is 1431, but France has fallen to an army of dragons led by a corrupted Jeanne d\'Arc. The Dragon Witch seeks revenge against the nation that burned her at the stake, commanding wyverns and evil servants to lay waste to the land.',
    sections: [
      {
        title: 'Historical Setting',
        content: 'Set during the final years of the Hundred Years\' War between France and England. Historically, Joan of Arc was captured in 1430 and executed in 1431. In this singularity, her hatred and despair have been twisted into a force of destruction.'
      },
      {
        title: 'Key Conflict',
        content: 'The true Jeanne d\'Arc, summoned as a Ruler-class Servant, must face her corrupted self while the protagonists rally the remaining French forces and heroic spirits to save the nation.'
      }
    ],
    historicalBasis: 'The Hundred Years\' War (1337-1453) was a series of conflicts between England and France. Joan of Arc, a peasant girl who claimed divine guidance, led French forces to several victories before her capture and execution. Her trial and burning at the stake in Rouen became one of history\'s most infamous cases of injustice.',
    relatedServants: [
      { name: 'Jeanne d\'Arc', class: 'Ruler', rarity: 5 },
      { name: 'Jeanne d\'Arc (Alter)', class: 'Avenger', rarity: 5 },
      { name: 'Marie Antoinette', class: 'Rider', rarity: 4 },
      { name: 'Chevalier d\'Eon', class: 'Saber', rarity: 4 },
      { name: 'Gilles de Rais', class: 'Caster', rarity: 3 }
    ],
    relatedEvents: [
      { id: 1, title: 'Siege of Orleans', year: 1429 },
      { id: 2, title: 'Execution of Joan of Arc', year: 1431 },
      { id: 3, title: 'End of Hundred Years\' War', year: 1453 }
    ],
    sources: ['Fate/Grand Order', 'Historical records of Joan of Arc', 'Hundred Years\' War documentation']
  },
  {
    id: 'singularity-7',
    type: 'singularity',
    title: 'Babylonia',
    subtitle: 'Absolute Demonic Front',
    chapter: 'Seventh Singularity',
    era: 'Ancient',
    year: -2655,
    location: 'Mesopotamia',
    description: 'The final singularity of the Grand Order. Mesopotamia in 2655 BC faces annihilation from the Beasts of Humanity. King Gilgamesh leads the last defense of human civilization against the goddess Tiamat and her Lahmu army.',
    sections: [
      {
        title: 'Historical Setting',
        content: 'Set in ancient Mesopotamia during the reign of Gilgamesh, King of Uruk. This is the cradle of civilization, where the earliest writing, laws, and urban centers emerged. The city of Uruk, protected by its mighty walls, stands as humanity\'s last bastion.'
      },
      {
        title: 'The Demonic Beasts',
        content: 'Three Goddesses from the Age of Gods have formed an alliance to destroy humanity. Gorgon, Quetzalcoatl, and Ereshkigal each control territories around Uruk, while the primordial goddess Tiamat awakens in the Persian Gulf.'
      }
    ],
    historicalBasis: 'Gilgamesh was a historical king of Uruk (c. 2900-2350 BC), later deified and made the hero of the Epic of Gilgamesh, one of humanity\'s oldest literary works. Mesopotamia (modern Iraq) is considered one of the birthplaces of human civilization.',
    relatedServants: [
      { name: 'Gilgamesh', class: 'Archer', rarity: 5 },
      { name: 'Enkidu', class: 'Lancer', rarity: 5 },
      { name: 'Ishtar', class: 'Archer', rarity: 5 },
      { name: 'Ereshkigal', class: 'Lancer', rarity: 5 },
      { name: 'Quetzalcoatl', class: 'Rider', rarity: 5 },
      { name: 'Merlin', class: 'Caster', rarity: 5 }
    ],
    relatedEvents: [
      { id: 4, title: 'Rise of Sumerian Civilization', year: -3500 },
      { id: 5, title: 'Epic of Gilgamesh composed', year: -2100 }
    ],
    sources: ['Fate/Grand Order', 'Epic of Gilgamesh', 'Sumerian mythology', 'Mesopotamian archaeology']
  }
]

// Lostbelt Data
export const lostbelts: ShowcaseContent[] = [
  {
    id: 'lostbelt-1',
    type: 'lostbelt',
    title: 'Anastasia',
    subtitle: 'Permafrost Empire',
    chapter: 'Lostbelt No.1',
    era: 'Modern (Divergent)',
    year: 1570,
    location: 'Russia',
    description: 'A world where Ivan the Terrible\'s experiments with the Yaga transformation succeeded, creating a frozen Russia where humans have merged with demonic beasts to survive an eternal winter.',
    sections: [
      {
        title: 'The Divergence',
        content: 'In 1570, Ivan the Terrible succeeded in his Oprichniki experiments, transforming his people into Yaga - human-beast hybrids capable of surviving the supernatural cold. This triggered a global ice age that never ended.'
      },
      {
        title: 'The Lostbelt King',
        content: 'Ivan the Terrible, now a massive mammoth-like creature, rules this frozen world from his Kremlin. Kept in eternal slumber by the tears of his Anastasia, he dreams of the warm Russia that once was.'
      }
    ],
    historicalBasis: 'Ivan IV "the Terrible" (1530-1584) was the first Tsar of Russia, known for his territorial expansion and the Oprichnina, a period of brutal political repression. Grand Duchess Anastasia Nikolaevna (1901-1918) was the youngest daughter of the last Tsar Nicholas II.',
    relatedServants: [
      { name: 'Anastasia', class: 'Caster', rarity: 5 },
      { name: 'Ivan the Terrible', class: 'Rider', rarity: 5 },
      { name: 'Atalante (Alter)', class: 'Berserker', rarity: 4 },
      { name: 'Avicebron', class: 'Caster', rarity: 3 }
    ],
    sources: ['Fate/Grand Order', 'Russian History', 'Romanov Dynasty records']
  },
  {
    id: 'lostbelt-5',
    type: 'lostbelt',
    title: 'Olympus',
    subtitle: 'Interstellar Mountainous City',
    chapter: 'Lostbelt No.5',
    era: 'Ancient (Divergent)',
    year: -12000,
    location: 'Atlantic Ocean / Greece',
    description: 'A world where the Age of Gods never ended and the Greek Olympians rule as the ultimate machine gods. The ancient war between the Titans and Olympians concluded differently, with the gods maintaining their mechanical divine forms.',
    sections: [
      {
        title: 'The Machine Gods',
        content: 'The Olympian Gods are revealed as alien machine intelligences that arrived on Earth in ancient times. In this Lostbelt, they never abandoned their true forms, ruling over a humanity that worships them as eternal gods.'
      },
      {
        title: 'Atlantis and Olympus',
        content: 'This Lostbelt spans two parts: Atlantis, the oceanic realm defended by Poseidon, and Olympus, the celestial city where Zeus holds absolute power. The protagonists must navigate both to challenge the King of the Gods.'
      }
    ],
    historicalBasis: 'Greek mythology describes the Titanomachy, the war between the Titans and Olympians for control of the cosmos. Atlantis is the legendary island civilization described by Plato, while Mount Olympus was the mythological home of the Greek gods.',
    relatedServants: [
      { name: 'Europa', class: 'Rider', rarity: 5 },
      { name: 'Caenis', class: 'Lancer', rarity: 5 },
      { name: 'Super Orion', class: 'Archer', rarity: 5 },
      { name: 'Romulus-Quirinus', class: 'Lancer', rarity: 5 }
    ],
    relatedEvents: [
      { id: 6, title: 'Titanomachy', year: -12000 },
      { id: 7, title: 'Fall of Atlantis (Plato)', year: -9600 }
    ],
    sources: ['Fate/Grand Order', 'Greek Mythology', 'Plato\'s Timaeus and Critias']
  }
]

// Servant Column Data
export const servantColumns: ShowcaseContent[] = [
  {
    id: 'servant-gilgamesh',
    type: 'servant',
    title: 'Gilgamesh - King of Heroes',
    subtitle: 'The oldest hero in human history',
    era: 'Ancient Mesopotamia',
    year: -2700,
    location: 'Uruk, Sumer',
    description: 'Gilgamesh, the demigod king of Uruk, is considered the oldest hero whose tale has survived in writing. Two-thirds divine and one-third human, he ruled Uruk with absolute power and embarked on legendary quests for immortality.',
    sections: [
      {
        title: 'Historical Background',
        content: 'Gilgamesh was a real historical figure, the fifth king of Uruk\'s First Dynasty (c. 2900-2350 BC). Archaeological evidence confirms Uruk\'s existence and its massive walls, credited to Gilgamesh in mythology. His legend was preserved in the Epic of Gilgamesh, written in Akkadian on clay tablets.'
      },
      {
        title: 'The Epic of Gilgamesh',
        content: 'The Epic describes Gilgamesh\'s friendship with Enkidu, their adventures fighting Humbaba and the Bull of Heaven, Enkidu\'s death, and Gilgamesh\'s failed quest for immortality. It contains the flood myth that predates the Biblical Noah story.'
      },
      {
        title: 'Fate Interpretation',
        content: 'In Fate, Gilgamesh wields the Gate of Babylon, containing all the prototypes of humanity\'s treasures. His arrogant personality reflects his legend as a tyrant who was eventually humbled by his journey. He appears as Archer class in most works.'
      }
    ],
    historicalBasis: 'The Epic of Gilgamesh, discovered in the library of Ashurbanipal in Nineveh (modern Mosul, Iraq), is among humanity\'s oldest literary works. Archaeological excavations at Uruk (modern Warka, Iraq) have revealed the ancient city\'s impressive scale.',
    relatedServants: [
      { name: 'Enkidu', class: 'Lancer', rarity: 5 },
      { name: 'Ishtar', class: 'Archer', rarity: 5 },
      { name: 'Siduri', class: 'NPC', rarity: 0 }
    ],
    relatedEvents: [
      { id: 4, title: 'Rise of Sumerian Civilization', year: -3500 },
      { id: 5, title: 'Epic of Gilgamesh composed', year: -2100 },
      { id: 8, title: 'Fall of Uruk to Babylon', year: -2004 }
    ],
    sources: [
      'Epic of Gilgamesh (Standard Babylonian Version)',
      'Sumerian King List',
      'Archaeological reports from Uruk/Warka',
      'Fate/stay night',
      'Fate/Grand Order'
    ]
  },
  {
    id: 'servant-leonidas',
    type: 'servant',
    title: 'Leonidas I - King of Sparta',
    subtitle: 'The warrior who defied an empire',
    era: 'Classical Greece',
    year: -480,
    location: 'Thermopylae, Greece',
    description: 'Leonidas I, King of Sparta, led 300 Spartans and their Greek allies against the massive Persian army at Thermopylae. His sacrifice became an eternal symbol of courage and duty in the face of overwhelming odds.',
    sections: [
      {
        title: 'The Battle of Thermopylae',
        content: 'In 480 BC, Persian King Xerxes invaded Greece with an army numbering in the hundreds of thousands. Leonidas led a force of 7,000 Greeks, including his 300 Spartiates, to hold the narrow pass at Thermopylae. They held for three days before being betrayed and surrounded.'
      },
      {
        title: 'Historical Legacy',
        content: 'Though the battle was a tactical defeat, it became a strategic victory. The delay allowed Greek states to prepare, leading to the Persian defeat at Salamis and Plataea. The epitaph "Go tell the Spartans..." became one of history\'s most famous inscriptions.'
      },
      {
        title: 'Fate Interpretation',
        content: 'In Fate, Leonidas is summoned as a Lancer-class Servant. His Noble Phantasm recreates the defensive formation of Thermopylae, embodying his legend as the ultimate guardian. Despite being a 2-star Servant, his gameplay reflects his legendary defensive capabilities.'
      }
    ],
    historicalBasis: 'Herodotus provides the primary account of Thermopylae in his Histories. Archaeological work at the site has confirmed the narrow pass and discovered artifacts from the battle. Spartan military training (agoge) and culture are well-documented.',
    relatedServants: [
      { name: 'Leonidas I', class: 'Lancer', rarity: 2 },
      { name: 'Iskandar', class: 'Rider', rarity: 5 },
      { name: 'Darius III', class: 'Berserker', rarity: 3 }
    ],
    relatedEvents: [
      { id: 9, title: 'Battle of Marathon', year: -490 },
      { id: 10, title: 'Battle of Thermopylae', year: -480 },
      { id: 11, title: 'Battle of Salamis', year: -480 },
      { id: 12, title: 'Battle of Plataea', year: -479 }
    ],
    sources: [
      'Herodotus - Histories',
      'Plutarch - Parallel Lives',
      'Diodorus Siculus',
      'Fate/Grand Order'
    ]
  }
]

// Pan-Human History - Historical Articles
export const historyArticles: ShowcaseContent[] = [
  {
    id: 'history-crusades',
    type: 'article',
    title: 'The Crusades',
    subtitle: 'Holy Wars that shaped medieval Europe and the Middle East',
    era: 'Medieval',
    year: 1095,
    location: 'Europe / Middle East',
    description: 'The Crusades were a series of religious wars initiated by the Latin Church in the medieval period. The most commonly known Crusades aimed to recover the Holy Land from Islamic rule.',
    sections: [
      {
        title: 'Origins',
        content: 'In 1095, Pope Urban II called for a military expedition to aid the Byzantine Empire and reclaim Jerusalem. His speech at the Council of Clermont ignited religious fervor across Europe, leading thousands to "take the cross."'
      },
      {
        title: 'Major Crusades',
        content: 'The First Crusade (1096-1099) successfully captured Jerusalem. The Third Crusade (1189-1192) saw legendary figures like Richard the Lionheart face Saladin. The Fourth Crusade (1202-1204) infamously sacked Constantinople instead of reaching the Holy Land.'
      },
      {
        title: 'Legacy',
        content: 'The Crusades facilitated cultural exchange, introduced new ideas, technologies, and goods to Europe, and permanently altered relations between Christianity and Islam.'
      }
    ],
    relatedServants: [
      { name: 'Richard I', class: 'Saber', rarity: 5 },
      { name: 'Saint George', class: 'Rider', rarity: 2 },
      { name: 'Saladin', class: 'Rider', rarity: 4 }
    ],
    relatedEvents: [
      { id: 101, title: 'Council of Clermont', year: 1095 },
      { id: 102, title: 'Siege of Jerusalem', year: 1099 },
      { id: 103, title: 'Battle of Hattin', year: 1187 },
      { id: 104, title: 'Siege of Acre', year: 1191 }
    ],
    sources: ['Chronicles of the Crusades', 'Historia Hierosolymitana', 'Arab historians']
  },
  {
    id: 'history-templars',
    type: 'article',
    title: 'Knights Templar',
    subtitle: 'The legendary warrior monks of the medieval era',
    era: 'Medieval',
    year: 1119,
    location: 'Jerusalem / Europe',
    description: 'The Poor Fellow-Soldiers of Christ and of the Temple of Solomon, commonly known as the Knights Templar, were among the most famous of the Western Christian military orders.',
    sections: [
      {
        title: 'Foundation',
        content: 'Founded around 1119 by Hugues de Payens and eight other knights, the order was endorsed by the Catholic Church and grew rapidly in membership and power. They were headquartered on Jerusalem\'s Temple Mount.'
      },
      {
        title: 'Power and Influence',
        content: 'The Templars developed innovative financial techniques that were an early form of banking, built a network of nearly 1,000 commanderies across Europe, and became one of the most powerful organizations in the medieval world.'
      },
      {
        title: 'The Fall',
        content: 'On Friday, October 13, 1307, King Philip IV of France had many Templars arrested, tortured, and burned at the stake. The order was dissolved by Pope Clement V in 1312, spawning centuries of legends and conspiracy theories.'
      }
    ],
    relatedEvents: [
      { id: 105, title: 'Founding of the Templars', year: 1119 },
      { id: 106, title: 'Council of Troyes', year: 1129 },
      { id: 107, title: 'Fall of Acre', year: 1291 },
      { id: 108, title: 'Arrest of the Templars', year: 1307 }
    ],
    sources: ['Rule of the Templars', 'Trial records', 'Medieval chronicles']
  },
  {
    id: 'history-alexanderthegreat',
    type: 'article',
    title: 'Alexander the Great',
    subtitle: 'The conqueror who forged the largest empire in ancient history',
    era: 'Classical',
    year: -356,
    location: 'Macedonia / Asia',
    description: 'Alexander III of Macedon, known as Alexander the Great, created one of the largest empires in history by the age of thirty, stretching from Greece to northwestern India.',
    sections: [
      {
        title: 'Rise to Power',
        content: 'Born in 356 BC, Alexander was tutored by Aristotle and succeeded his father Philip II at age 20. He immediately consolidated power in Greece before turning his attention eastward.'
      },
      {
        title: 'Conquests',
        content: 'His military campaigns took him across Persia, Egypt, Central Asia, and into India. Key battles include Granicus (334 BC), Issus (333 BC), Gaugamela (331 BC), and the Hydaspes (326 BC).'
      },
      {
        title: 'Legacy',
        content: 'Alexander spread Greek culture across his empire, founding numerous cities (including Alexandria in Egypt). His death at 32 led to the division of his empire among his generals, establishing the Hellenistic period.'
      }
    ],
    relatedServants: [
      { name: 'Iskandar', class: 'Rider', rarity: 5 },
      { name: 'Hephaestion', class: 'Lancer', rarity: 4 },
      { name: 'Darius III', class: 'Berserker', rarity: 3 }
    ],
    relatedEvents: [
      { id: 109, title: 'Battle of Granicus', year: -334 },
      { id: 110, title: 'Battle of Issus', year: -333 },
      { id: 111, title: 'Siege of Tyre', year: -332 },
      { id: 112, title: 'Battle of Gaugamela', year: -331 }
    ],
    sources: ['Arrian - Anabasis', 'Plutarch - Life of Alexander', 'Diodorus Siculus']
  }
]

// Pan-Human History - Literature Articles
export const literatureArticles: ShowcaseContent[] = [
  {
    id: 'literature-iliad',
    type: 'article',
    title: 'The Iliad',
    subtitle: 'Homer\'s epic poem of the Trojan War',
    era: 'Classical',
    year: -750,
    location: 'Greece / Troy',
    description: 'The Iliad is an ancient Greek epic poem attributed to Homer, set during the Trojan War. It tells of the battles and events during the weeks of a quarrel between King Agamemnon and the warrior Achilles.',
    sections: [
      {
        title: 'The Story',
        content: 'The poem covers a few weeks in the final year of the Trojan War. It begins with Achilles\' anger at Agamemnon and ends with the funeral of Hector. The famous wooden horse and fall of Troy are not directly depicted.'
      },
      {
        title: 'Major Characters',
        content: 'Greek heroes include Achilles, Odysseus, Ajax, and Diomedes. Trojan defenders feature Hector, Paris, and Priam. The gods—Zeus, Athena, Apollo, Aphrodite—actively participate in the conflict.'
      },
      {
        title: 'Literary Significance',
        content: 'Considered one of the oldest works of Western literature, the Iliad has profoundly influenced art, literature, and philosophy for nearly three millennia.'
      }
    ],
    relatedServants: [
      { name: 'Achilles', class: 'Rider', rarity: 5 },
      { name: 'Hector', class: 'Lancer', rarity: 4 },
      { name: 'Paris', class: 'Archer', rarity: 4 },
      { name: 'Odysseus', class: 'Rider', rarity: 5 }
    ],
    relatedEvents: [
      { id: 113, title: 'Trojan War begins', year: -1194 },
      { id: 114, title: 'Death of Patroclus', year: -1184 },
      { id: 115, title: 'Death of Hector', year: -1184 },
      { id: 116, title: 'Fall of Troy', year: -1184 }
    ],
    sources: ['Homer - Iliad', 'Archaeological findings at Hisarlik', 'Ancient Greek tradition']
  },
  {
    id: 'literature-arthurian',
    type: 'article',
    title: 'Arthurian Legend',
    subtitle: 'The Matter of Britain and the Knights of the Round Table',
    era: 'Medieval',
    year: 500,
    location: 'Britain',
    description: 'The legends of King Arthur, Camelot, and the Knights of the Round Table form one of the most influential bodies of mythology in Western literature.',
    sections: [
      {
        title: 'Historical Basis',
        content: 'Whether Arthur was a real person remains debated. If he existed, he likely lived around 500 AD as a Romano-British war leader fighting Saxon invaders. The legends grew over centuries.'
      },
      {
        title: 'Key Elements',
        content: 'The sword Excalibur, the wizard Merlin, the Round Table, the quest for the Holy Grail, the love triangle of Arthur, Guinevere, and Lancelot—these elements have been retold countless times.'
      },
      {
        title: 'Literary Evolution',
        content: 'From Geoffrey of Monmouth\'s Historia Regum Britanniae to Chrétien de Troyes\' romances to Malory\'s Le Morte d\'Arthur, the legend evolved to reflect different eras\' ideals.'
      }
    ],
    relatedServants: [
      { name: 'Artoria Pendragon', class: 'Saber', rarity: 5 },
      { name: 'Merlin', class: 'Caster', rarity: 5 },
      { name: 'Lancelot', class: 'Saber', rarity: 4 },
      { name: 'Gawain', class: 'Saber', rarity: 4 },
      { name: 'Mordred', class: 'Saber', rarity: 5 },
      { name: 'Tristan', class: 'Archer', rarity: 4 }
    ],
    relatedEvents: [
      { id: 117, title: 'Battle of Badon Hill', year: 500 },
      { id: 118, title: 'Battle of Camlann', year: 537 }
    ],
    sources: ['Geoffrey of Monmouth', 'Chrétien de Troyes', 'Thomas Malory - Le Morte d\'Arthur']
  },
  {
    id: 'literature-journey-west',
    type: 'article',
    title: 'Journey to the West',
    subtitle: 'The legendary pilgrimage of Xuanzang and Sun Wukong',
    era: 'Ancient',
    year: 629,
    location: 'China / India',
    description: 'Journey to the West is one of the Four Great Classical Novels of Chinese literature, telling the fictionalized story of the Buddhist monk Xuanzang\'s pilgrimage to India, accompanied by three supernatural disciples.',
    sections: [
      {
        title: 'Historical Basis',
        content: 'The real Xuanzang (602-664) was a Chinese Buddhist monk who traveled to India to obtain sacred texts. His journey (629-645) covered over 10,000 miles and was recorded in "Great Tang Records on the Western Regions."'
      },
      {
        title: 'The Novel',
        content: 'Written in the 16th century (attributed to Wu Cheng\'en), the novel adds the Monkey King Sun Wukong, Zhu Bajie (Pigsy), and Sha Wujing (Sandy) as magical companions who help Xuanzang overcome 81 tribulations.'
      },
      {
        title: 'Cultural Impact',
        content: 'Sun Wukong has become one of the most enduring characters in East Asian culture, inspiring countless adaptations in literature, theater, film, anime, and video games.'
      }
    ],
    relatedServants: [
      { name: 'Xuanzang', class: 'Caster', rarity: 5 }
    ],
    relatedEvents: [
      { id: 119, title: 'Xuanzang\'s departure', year: 629 },
      { id: 120, title: 'Arrival at Nalanda', year: 637 },
      { id: 121, title: 'Return to Chang\'an', year: 645 }
    ],
    sources: ['Journey to the West (novel)', 'Great Tang Records on the Western Regions', 'Chinese Buddhist history']
  }
]

// Pan-Human History - Music Articles
export const musicArticles: ShowcaseContent[] = [
  {
    id: 'music-mozart',
    type: 'article',
    title: 'Wolfgang Amadeus Mozart',
    subtitle: 'The prodigy who defined Classical music',
    era: 'Early Modern',
    year: 1756,
    location: 'Salzburg / Vienna',
    description: 'Mozart was a prolific and influential composer of the Classical period who composed over 600 works during his short life of 35 years, including symphonies, operas, and chamber music.',
    sections: [
      {
        title: 'Child Prodigy',
        content: 'Mozart showed exceptional musical ability from age 3, composing from age 5 and touring European courts as a child. His father Leopold promoted him as a miraculous talent.'
      },
      {
        title: 'Major Works',
        content: 'His operas include The Marriage of Figaro, Don Giovanni, and The Magic Flute. His final work, the Requiem in D minor, remained unfinished at his death and has inspired many legends.'
      },
      {
        title: 'Legacy',
        content: 'Mozart\'s music represents the height of the Classical style. His influence on subsequent composers, from Beethoven to modern times, is immeasurable.'
      }
    ],
    relatedServants: [
      { name: 'Amadeus Mozart', class: 'Caster', rarity: 4 },
      { name: 'Antonio Salieri', class: 'Avenger', rarity: 3 },
      { name: 'Marie Antoinette', class: 'Rider', rarity: 4 }
    ],
    relatedEvents: [
      { id: 122, title: 'Mozart\'s birth', year: 1756 },
      { id: 123, title: 'First European tour', year: 1762 },
      { id: 124, title: 'Premiere of Don Giovanni', year: 1787 },
      { id: 125, title: 'Mozart\'s death', year: 1791 }
    ],
    sources: ['Mozart\'s letters', 'Contemporary accounts', 'Musical manuscripts']
  },
  {
    id: 'music-beethoven',
    type: 'article',
    title: 'Ludwig van Beethoven',
    subtitle: 'The revolutionary who bridged Classical and Romantic eras',
    era: 'Modern',
    year: 1770,
    location: 'Bonn / Vienna',
    description: 'Beethoven was a German composer and pianist who remains one of the most admired composers in the history of Western music. He continued to compose masterpieces even after becoming deaf.',
    sections: [
      {
        title: 'Early Life',
        content: 'Born in Bonn, Beethoven moved to Vienna in 1792, initially studying with Haydn. He quickly established himself as a virtuoso pianist and daring composer.'
      },
      {
        title: 'Overcoming Deafness',
        content: 'Beethoven began losing his hearing in his late 20s. His famous "Heiligenstadt Testament" reveals his despair, yet he continued composing, producing his greatest works while substantially or completely deaf.'
      },
      {
        title: 'Revolutionary Works',
        content: 'His Ninth Symphony, with its "Ode to Joy," broke all conventions. His 32 piano sonatas and string quartets remain cornerstones of the repertoire.'
      }
    ],
    relatedEvents: [
      { id: 126, title: 'Beethoven\'s birth', year: 1770 },
      { id: 127, title: 'Premiere of Symphony No. 3 "Eroica"', year: 1805 },
      { id: 128, title: 'Premiere of Symphony No. 9', year: 1824 },
      { id: 129, title: 'Beethoven\'s death', year: 1827 }
    ],
    sources: ['Beethoven\'s letters', 'Contemporary accounts', 'Musical manuscripts']
  },
  {
    id: 'music-phantom',
    type: 'article',
    title: 'The Phantom of the Opera',
    subtitle: 'From French novel to legendary musical',
    era: 'Modern',
    year: 1910,
    location: 'Paris Opera House',
    description: 'The Phantom of the Opera began as a serialized French novel by Gaston Leroux, inspired by real events at the Paris Opera, and became one of the most successful musicals in history.',
    sections: [
      {
        title: 'The Original Novel',
        content: 'Gaston Leroux published "Le Fantôme de l\'Opéra" in 1910. The story of Erik, a disfigured musical genius living beneath the Paris Opera, was inspired by real incidents including a chandelier accident in 1896.'
      },
      {
        title: 'Real History',
        content: 'The Palais Garnier, opened in 1875, does have underground levels and a subterranean lake. Leroux wove fact and fiction brilliantly.'
      },
      {
        title: 'Andrew Lloyd Webber\'s Musical',
        content: 'The 1986 musical became the longest-running show in Broadway history. Its iconic imagery—the mask, the chandelier, the underground lair—has become part of popular culture.'
      }
    ],
    relatedServants: [
      { name: 'Phantom of the Opera', class: 'Assassin', rarity: 2 },
      { name: 'Christine Daaé', class: 'Caster', rarity: 3 }
    ],
    relatedEvents: [
      { id: 130, title: 'Palais Garnier opens', year: 1875 },
      { id: 131, title: 'Chandelier accident', year: 1896 },
      { id: 132, title: 'Novel published', year: 1910 },
      { id: 133, title: 'Lloyd Webber musical premieres', year: 1986 }
    ],
    sources: ['Gaston Leroux - Le Fantôme de l\'Opéra', 'Paris Opera archives', 'Musical history']
  }
]

// Helper function to get all showcase content
export function getAllShowcaseContent(): ShowcaseContent[] {
  return [
    ...singularities,
    ...lostbelts,
    ...servantColumns,
    ...historyArticles,
    ...literatureArticles,
    ...musicArticles
  ]
}

// Helper function to get content by ID
export function getShowcaseContentById(id: string): ShowcaseContent | undefined {
  return getAllShowcaseContent().find(content => content.id === id)
}
