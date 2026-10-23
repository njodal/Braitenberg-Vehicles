# Modules

## Summary

A **module** is a piece of nervous system in a file of its own, which any vehicle can include and wire into its brain. It has a few **inputs**, through which the vehicle's units drive it, turning it on or off, and a few **outputs**, which the vehicle connects to its motors or units. Inside, it is made of ordinary units.

Braitenberg builds every vehicle from the same few parts, and many of his circuits are useful in more than one vehicle. Until now each vehicle has to write its circuits out in full, so a behavior designed for one vehicle, such as the Vehicle 8 hunter's wandering, is copied by hand into another. A module is written once and included wherever it is needed.

For example, the module [wander](../modules/wander.yaml) defines the ensemble of units that makes the vehicle move slowly and sideways in an almost random way. It is made of threshold units only, and the vehicle turns it on through its only input, `enable` (see *The wander module*). The first vehicle to use it is [vehicle 8](vehicle-08.md), which turns it on when it has seen nothing move for a while (*Searching*). The same vehicle uses two more modules: [boredom](../modules/boredom.yaml), which tells it when it has seen nothing for a while (see *The boredom module*), and [pursue](../modules/pursue.yaml), which turns toward what moves and lunges at it (see *The pursue module*).

## Module files

A module file has three sections:

```yaml
module:
  name: Wander
  description: Now and then, a short pulse on left or right, while enabled.

inputs:
  enable: while it carries a signal, the module fires now and then; without it, never

outputs: [left, right]

units:
  - unit:
      name: tick
      type: threshold
      threshold: 2
      inputs:
        - input:
            from: both            # one of the module's units
        - input:
            from: was
            type: inhibitory
        - input:
            from: enable          # one of its inputs
  - unit:
      name: left
      type: threshold
      threshold: 1
      delay: 0.4
      inputs:
        - input:
            from: go_left
  ...
```

| Key | Required | Meaning |
|---|---|---|
| `module.name` | yes | Human-readable name, e.g. `Wander`. |
| `module.description` | no | Free text. |
| `inputs` | yes | A mapping from each input's name to a description of what it does. A module may have no inputs (`{}`): a unit with threshold 0 then fires on its own. |
| `outputs` | yes | The names of the units that the vehicle may connect to. At least one. |
| `units` | yes | The module's units, written as in a vehicle definition ([vehicle-definition.md](vehicle-definition.md), *4. Units*), including arrays. |

Inside a module, a unit's inputs come from the module's own units or from its inputs, by name. A module has no sensors and no motors: it reaches the world only through the vehicle that includes it. Names of units and inputs follow the rules for names in a definition, and an input and a unit cannot share a name. Avoid names that YAML reads as booleans, such as `on`, `off`, `yes` and `no`: as keys they are read as `true` and `false`.

A module's units have no `position`: the diagram draws the whole module as one part, where the vehicle puts it (see below).

## Including a module

A vehicle definition includes modules in an optional top-level section, `modules`:

```yaml
modules:
  - module:
      name: pursue                    # how the vehicle names this copy
      file: ../modules/pursue.yaml    # relative to the definition file
      position: [0.12, -0.68]
      inputs:
        left: [moves_left, wander.left]     # several sources: any of them
        ahead: moves_ahead                  # one source
        right: [moves_right, wander.right]
        near: near
  - module:
      name: wander
      file: ../modules/wander.yaml
      position: [-0.66, -0.66]
      inputs:
        enable: boredom.bored         # another module's output
```

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | The name of this copy of the module, unique among the vehicle's sensors, actuators, units and modules. |
| `file` | yes | The module file, relative to the definition. |
| `position` | no | Where the diagram draws the module, in body coordinates. Default `[0, 0]`. |
| `inputs` | yes | For every input of the module, where it comes from: a `from` as in any input (`moves_ahead`, `retina[:, 0:6]`, another module's output) or a list of them, possibly empty. Every input of the module must be given, and no other. |

A vehicle may include the same module file more than once, under different names; each copy has its own units.

### What including means

Including a module is the same as writing its units into the vehicle's `units`, renamed, and wired:

- Each unit `u` of the module becomes a unit named `name.u` of the vehicle, such as `wander.left`. Its inputs from the module's own units come from their renamed copies.
- An input of a unit from the module's input `x` becomes one input per source that the vehicle gives `x`, each with the type and strength written in the module. An input with no sources gives no inputs: a wander module whose `enable` is `[]` never fires.
- Outside the module, the vehicle's units and actuators connect to its outputs as `name.output`, such as `from: wander.left`. Only outputs can be named; the module's other units are private to it.

So a module adds no new kind of part to the simulation: a vehicle with a module behaves exactly as the same vehicle with the module's units written out by hand.

### In the diagram

The diagram draws a module as one part, at its `position`: a box, with its inputs on top and its outputs below, in the order of the module file, each a small circle with its name beside it. Inside the box, in the middle, are the module's name in the vehicle, in bold, and below it `module` and the module's own name (`wander`, `module Wander`); they are drawn over the wires, so that a wire crossing the box does not hide them. Its units and the wires between them are not drawn: from outside, a module is what goes in and what comes out. A wire into the module ends at the input it comes through, and a wire out of it starts at its output. The box is drawn under the wires, so that a wire is seen leaving its output even when it goes up. In the panel, where there is less room, the box is smaller, with only its name inside and its ports as small circles, each output lit by its level; the readouts show one line for the module, with its outputs as cells ([vehicle-diagram.md](vehicle-diagram.md)).

![Diagram of the Vehicle 8 hunter, drawn by python -m braitenberg.diagram: below the movement detectors, on the left, the boredom module above the wander module; in the middle, the pursue module, with its inputs left, ahead, right and near on top and its outputs turn_left, turn_right and forward below, wired to the motors](images/vehicle8-hunter.svg)

*The Vehicle 8 hunter, which includes three modules ([vehicle-08.md](vehicle-08.md)). On the left, `boredom` takes the movement detectors through `seen` and `acting` through `busy`, and its output `bored` enables `wander`, below it. In the middle, `pursue` takes `moves_left`, `moves_ahead`, `moves_right` and `near` through its inputs, and its outputs drive the motors. `wander`'s outputs go to `acting` and into `pursue`'s inputs `left` and `right`, so that a wandering turn is a turn of `pursue`. The units inside the modules are not drawn.*

### Turning a module on and off

A module is switched on and off by its inputs, like any unit. The convention for a module that is a behavior is one input, `enable`: the module acts while it carries a signal, and stays quiet without it. Any unit of the vehicle can drive it: a threshold unit that fires when nothing has been seen for a while, a sensor, or another module's output. Several sources given to `enable` add up, so any one of them turns the module on.

When the module should stop for other reasons too, the vehicle says so with a unit of its own, or another module, and gives it to `enable`. The Vehicle 8 hunter wanders only while it has seen nothing move for a while and is still: the module `boredom` decides that, and its output `bored` enables `wander`. So a module knows only when to act, and the vehicle decides why.

## The wander module

`modules/wander.yaml` makes a vehicle wander with nothing but threshold units: there is no chance in it, but its pulses come at moments, and to sides, that follow no simple rhythm.

- **Clocks:** a unit with threshold 0 and an inhibitory input from itself fires on its own, silences itself, and fires again: it is on for its delay and off for about twice that. `fast` (delay 0.45 s) and `slow` (0.7 s) are two such clocks. `ring` and `side` (0.95 s each) are a ring of two, `ring` silenced by `side` and `side` driven by `ring`, so that `side` is on and off for about as long.
- **When:** `both` fires while `fast` and `slow` are on together. Their periods have no small common multiple, so this happens at irregular moments, every 2.3 s on average and never less than 1 s apart. `tick` fires for a moment as `both` comes on (`was`, a copy of `both` one delay late, stops it), while `enable` is on.
- **Which side:** `go_left` fires with `tick` while `side` is on, `go_right` while it is off. `side` keeps its own rhythm, so the sides follow no short pattern, and come about as often.
- **How long:** `left` and `right` stretch the moment into a pulse of about 0.4 s, their delay.

Seen from outside, it behaves like a coin tossed now and then: about 130 pulses in 300 s, close to half to each side, with no repeating pattern of a few turns. But the same start always gives the same pulses: a vehicle that uses it behaves the same in every run, whatever the seed.

## The boredom module

`modules/boredom.yaml` tells a vehicle that nothing has happened for a while. It is made of seven threshold units:

- **Inputs:** `seen`, something seen, such as movement; and `busy`, the vehicle is busy, such as moving.
- **Output:** `bored`, which fires 3.2 s after `seen` last carried a signal, however long it lasted, while `busy` is off.
- **A ladder of delays:** a unit with threshold 0 and an inhibitory input from `seen` fires on its own unless something was seen during its delay, and its output comes a delay later: it says that nothing was seen between twice its delay and its delay ago. `quiet_1` to `quiet_6` have delays of 0.05, 0.1, 0.2, 0.4, 0.8 and 1.6 s, doubling, so that their spans meet without gaps and together cover the last 3.2 s.
- **Bored:** `bored` needs all six, and is held back by `seen` and `busy` directly, so that it stops at once when something is seen or the vehicle moves.

A single unit with a long delay would not do: its output tells what happened a delay ago, so for a whole delay after something is seen it still says that nothing was. A memory that holds itself on would not do either: a unit that clears it would itself be a delay late, and wipe out the memory of something seen only briefly. The ladder has neither problem: the shortest rungs notice at once, and the longest remember.

## The pursue module

`modules/pursue.yaml` turns a vehicle toward something on one side and lunges at something ahead. It is the Vehicle 8 hunter's chase ([vehicle-08.md](vehicle-08.md), *Units*), made into a module.

- **Inputs:** `left`, `ahead` and `right`, where there is something to go for, and `near`, that what is ahead is already close.
- **Outputs:** `turn_left`, `turn_right` and `forward`, which the vehicle wires to its motors: a turn to the left drives the right motor, and `forward` drives both.
- **Turns** (`turn_left`, `turn_right`, delay 0.1 s) fire on their side unless something is also ahead. They are short, so as not to swing past what is only a little to one side.
- **Lunges** (`forward`, delay 0.3 s) fire on `ahead`, unless `near`. They are longer, to gain on what never stops.

Each command lasts about twice its delay longer than the signal that called for it, as for any unit. What the inputs mean is up to the vehicle: the hunter gives `left` both the movement it sees on the left and the left pulses of `wander`, so that its wandering turns are made by `pursue` too.

## Loading and validation

Loading fails, naming the file and the key, when:

- the module file is missing, or is not valid YAML;
- in the module file: `module`, `inputs`, `outputs` or `units` is missing, has the wrong type, or an unknown key appears; an input or unit name is not a valid name, or an input and a unit share a name; an output is not one of its units; a unit's input comes from something that is neither one of its units nor one of its inputs, or indexes an input; a unit has a `position`; or a unit is invalid as in a definition;
- in the definition: a module's `name` is not a valid name, or is already used; `file` or `inputs` is missing, or an unknown key appears; an input of the module is not given, or one is given that the module does not have; a source given to an input is not a sensor, unit or module output of the vehicle; a unit or actuator names a module's unit that is not an output, or a module that the vehicle does not include; or the module's `position` is outside the body.

## Acceptance criteria

1. **Loading:** a definition that includes `modules/wander.yaml` loads with its units renamed, such as `wander.left` and `wander.tick`, all threshold units; `wander.tick` has inputs from `wander.both` and `wander.was` and from each source the definition gives `enable`.
2. **Same as by hand:** the Vehicle 8 hunter, which includes both modules, and the same hunter with the modules' units written out by hand produce the same trajectory for the same seed.
3. **On and off:** a vehicle whose `enable` comes from a sensor wanders while the sensor reads 1: in 300 s, `left` and `right` together come on 100 to 160 times, each side 40% to 60% of them, never less than 1 s apart, each for about 0.4 s, and in no repeating pattern of up to 8 turns. While the sensor reads 0 they never fire, and with `enable` given as `[]` they never fire.
4. **Boredom:** with `seen` on for 0.05, 0.3, 1 or 3 s and then off, `bored` fires again 3.2 to 3.3 s after `seen` went off, and not before. It stops when `seen` or `busy` comes on, and stays off while `busy` is on.
5. **Pursue:** with steady inputs, `pursue` fires `turn_left` for `left`, `turn_right` for `right`, and `forward` for `ahead`, also when `left` is on too; nothing for `ahead` with `near`, nor with no input. A one-step signal on `left` gives a turn of 0.1 s, and one on `ahead` a lunge of 0.3 s.
6. **Two copies:** a vehicle that includes the module twice, as `a` and `b`, has units `a.left`, `a.right`, `b.left` and `b.right`, wired to their own inputs.
7. **Private units:** naming a module's unit that is not an output, from outside the module, is an error.
8. **Validation:** each failure case under *Loading and validation* raises an error naming the file and the key.
9. **Diagram:** the diagram of a vehicle with the wander module has one part `wander`, of kind `module`, at the module's position, with input `enable` and outputs `left` and `right`, and no part for its units. Its wires are only those that cross its edge: each one into it names the input it comes through, and each one out of it the output it comes from. The SVG draws the box with the names of its inputs and outputs.
10. **Headless:** loading a definition with modules never imports pygame.

## Out of scope

- **Parameters:** a module whose units take values from the including vehicle, such as other delays for each copy. A vehicle that needs other values uses another module file.
- **Modules inside modules**, sensors and motors in modules, and modules shared between vehicles at run time: each vehicle has its own copy.
- **Opening a module** in the diagram, to see its units and their wires.
