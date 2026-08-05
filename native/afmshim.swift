// afmshim : pont vers Apple Intelligence (FoundationModels) pour local-flow.
//
// Protocole : JSON sur stdin -> JSON sur stdout, un appel par process.
//   entree  : {"task": "probe"|"correct"|"translate"|"pro"|"friendly",
//              "text": "...", "lang": "en", "context": "...", "profile": "..."}
//   sortie  : {"ok": true, "text": "..."} ou {"ok": false, "error": "..."}
//
// Tout tourne on-device (modele systeme ~3B gere par macOS, zero RAM residente
// pour local-flow). Compile automatiquement par localflow/ai.py via swiftc.

import Foundation
import FoundationModels

func emit(_ obj: [String: Any]) {
    let d = try! JSONSerialization.data(withJSONObject: obj)
    print(String(data: d, encoding: .utf8)!)
}

func fail(_ msg: String) {
    emit(["ok": false, "error": msg])
}

let LANG_NAMES = [
    "en": "anglais", "es": "espagnol", "de": "allemand",
    "it": "italien", "pt": "portugais", "fr": "francais",
]

@main
struct Shim {
    static func main() async {
        guard #available(macOS 26.0, *) else {
            fail("macOS 26 requis pour Apple Intelligence")
            return
        }
        switch SystemLanguageModel.default.availability {
        case .available:
            break
        case .unavailable(let reason):
            fail("Apple Intelligence indisponible : \(reason)")
            return
        @unknown default:
            fail("Apple Intelligence indisponible")
            return
        }

        let input = FileHandle.standardInput.readDataToEndOfFile()
        guard let obj = try? JSONSerialization.jsonObject(with: input) as? [String: Any],
              let task = obj["task"] as? String else {
            fail("entree invalide")
            return
        }
        if task == "probe" {
            emit(["ok": true, "text": "ready"])
            return
        }
        guard let text = obj["text"] as? String, !text.isEmpty else {
            fail("texte manquant")
            return
        }
        let lang = obj["lang"] as? String ?? "en"
        let context = obj["context"] as? String ?? ""
        let profile = obj["profile"] as? String ?? ""

        var instructions: String
        var prompt: String

        switch task {
        case "correct":
            instructions = """
            Tu corriges des textes issus de dictee vocale. Ils contiennent souvent : tics oraux (euh, bah, hein), graphies phonetiques (passque = parce que, chuis = je suis, y'a = il y a), accords manques, ponctuation absente.
            Regles strictes :
            - Corrige orthographe, grammaire, ponctuation, graphies phonetiques.
            - Supprime les tics oraux.
            - Ne change JAMAIS le sens, le ton, ni la langue. Ne reformule pas, ne resume pas, n'ajoute rien.
            - Reponds UNIQUEMENT avec le texte corrige, sans guillemets ni commentaire.
            Exemple :
            Texte : alors euh je passe te voir demain passque j'ai fini tot
            Reponse : Alors je passe te voir demain parce que j'ai fini tôt.
            """
            prompt = "Texte : \(text)"
        case "translate":
            let name = LANG_NAMES[lang] ?? lang
            instructions = """
            Tu traduis fidelement des messages. Conserve le ton, le registre et toutes les informations. N'ajoute rien.
            Reponds UNIQUEMENT avec la traduction, sans guillemets ni commentaire.
            """
            prompt = "Traduis en \(name) : \(text)"
        case "pro":
            instructions = """
            Tu reecris des messages dans un registre professionnel courtois (email de travail).
            Regles strictes :
            - Conserve TOUTES les informations et demandes du texte original. N'invente aucun fait, aucun remerciement, aucune excuse qui n'y figure pas.
            - Vouvoiement, formules sobres. Meme langue que l'original. Pas de genre suppose pour l'auteur.
            - Reponds UNIQUEMENT avec le texte reecrit, sans objet ni signature, sans guillemets ni commentaire.
            Exemple :
            Texte : salut ton outil marche pas je comprends rien tu peux regarder
            Reponse : Bonjour, je rencontre un problème avec votre outil et je ne parviens pas à comprendre son fonctionnement. Pourriez-vous y jeter un œil ? Merci d'avance.
            """
            prompt = "Texte : \(text)"
        case "friendly":
            instructions = """
            Tu reecris des messages dans un registre amical et naturel, comme un SMS a un proche : tutoiement, ton detendu, phrases courtes, contractions orales bienvenues.
            Regles strictes :
            - Conserve TOUTES les informations du texte original. N'invente rien.
            - Meme langue que l'original.
            - Reponds UNIQUEMENT avec le texte reecrit, sans guillemets ni commentaire.
            Exemple :
            Texte : Je vous informe que je serai en retard d'environ quinze minutes.
            Reponse : Petit retard de ma part, j'arrive dans 15 min !
            """
            prompt = "Texte : \(text)"
        default:
            fail("tache inconnue : \(task)")
            return
        }

        if !profile.isEmpty {
            instructions += "\nHabitudes d'ecriture de l'utilisateur (a imiter quand c'est pertinent) : \(profile)"
        }
        if !context.isEmpty && (task == "friendly" || task == "pro") {
            prompt = "Derniers messages de la conversation (adapte ton registre a cet echange) :\n\(context)\n\n" + prompt
        }

        let session = LanguageModelSession(instructions: instructions)
        do {
            let r = try await session.respond(
                to: prompt,
                options: GenerationOptions(sampling: .greedy)
            )
            let out = r.content.trimmingCharacters(in: .whitespacesAndNewlines)
            emit(["ok": true, "text": out])
        } catch let e as LanguageModelSession.GenerationError {
            switch e {
            case .guardrailViolation:
                fail("refuse par les garde-fous Apple Intelligence")
            case .exceededContextWindowSize:
                fail("texte trop long pour le modele")
            default:
                fail("erreur du modele : \(e)")
            }
        } catch {
            fail("erreur du modele : \(error)")
        }
    }
}
