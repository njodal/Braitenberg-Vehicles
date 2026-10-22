# Modules

## Summary

A **module** is a piece of nervous system in a file of its own, which any vehicle can include and wire into its brain. It has a few **inputs**, through which the vehicle's units drive it, turning it on or off, and a few **outputs**, which the vehicle connects to its motors or units. Inside, it is made of ordinary units.

Braitenberg builds every vehicle from the same few parts, and many of his circuits are useful in more than one vehicle. Until now each vehicle has to write its circuits out in full, so a behavior designed for one vehicle, such as the Vehicle 8 hunter's wandering, is copied by hand into another. A module is written once and included wherever it is needed.

The first module is `modules/wander.yaml`: while its input `enable` carries a signal, and its input `hold` does not, it fires its output `left` or `right` now and then, for a short while, at moments and to sides that follow no simple rhythm. A vehicle that turns with those outputs wanders slowly in a direction that keeps changing. It is made of threshold units only, like every module (see *The wander module*). The Vehicle 8 hunter turns it on when it has seen nothing move for a while ([vehicle-08.md](vehicle-08.md), *Searching*).

## Module files

A module file has three sections:

```yaml
module:
  name: Wander
  description: Now and then, a short pulse on left or right, while enabled.

inputs:
  enable: while it carries a signal, the module may fire
  hold: while it carries a signal, the module waits

outputs: [left, right]

units:
  - unit:
      name: tick
      type: threshold
      threshold: 2
      position: [0, 0]
      inputs:
        - input:
            from: both            # one of the module's units
        - input:
            from: was
            type: inhibitory
        - input:
            from: enable          # one of its inputs
        - input:
            from: hold
            type: inhibitory
  - unit:
      name: left
      type: threshold
      threshold: 1
      delay: 0.4
      position: [-0.4, -0.08]
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
      name: wander                    # how the vehicle names this copy
      file: ../modules/wander.yaml    # relative to the definition file
      position: [0, -0.95]
      inputs:
        enable: search                # one source
        hold: [alert, acting]         # several, or [] for none
```

| Key | Required | Meaning |
|---|---|---|
| `name` | yes | The name of this copy of the module, unique among the vehicle's sensors, actuators, units and modules. |
| `file` | yes | The module file, relative to the definition. |
| `position` | no | Where the diagram draws the module, in body coordinates. Default `[0, 0]`. |
| `inputs` | yes | For every input of the module, where it comes from: a `from` as in any input (`search`, `retina[:, 0:6]`, another module's output) or a list of them, possibly empty. Every input of the module must be given, and no other. |

A vehicle may include the same module file more than once, under different names; each copy has its own units.

### What including means

Including a module is the same as writing its units into the vehicle's `units`, renamed, and wired:

- Each unit `u` of the module becomes a unit named `name.u` of the vehicle, such as `wander.left`. Its inputs from the module's own units come from their renamed copies.
- An input of a unit from the module's input `x` becomes one input per source that the vehicle gives `x`, each with the type and strength written in the module. An input with no sources gives no inputs: a unit whose `hold` is `[]` is never held back.
- Outside the module, the vehicle's units and actuators connect to its outputs as `name.output`, such as `from: wander.left`. Only outputs can be named; the module's other units are private to it.

So a module adds no new kind of part to the simulation: a vehicle with a module behaves exactly as the same vehicle with the module's units written out by hand.

### In the diagram

The diagram draws a module as one part, at its `position`: a strip of cells, one per unit in the order of the module file, each lit by its unit's output, labeled with the module's name in the vehicle and, below it, `module` and the module's own name (`wander`, `module Wander`). Wires inside the module are not drawn; a wire into or out of it starts or ends at the strip, and one out of it starts at its output's cell. The readouts show one line for it, with its cells, as for an array ([vehicle-diagram.md](vehicle-diagram.md)).

### Turning a module on and off

A module is switched on and off by its inputs, like any unit. The convention for modules that are behaviors is an input `enable`, that lets the module act while it carries a signal, and an input `hold`, that stops it while it carries one. Any unit of the vehicle can drive them: a threshold unit that fires when nothing has been seen for a while, a sensor, or another module's output.

## The wander module

`modules/wander.yaml` makes a vehicle wander with nothing but threshold units: there is no chance in it, but its pulses come at moments, and to sides, that follow no simple rhythm.

- **Clocks:** a unit with threshold 0 and an inhibitory input from itself fires on its own, silences itself, and fires again: it is on for its delay and off for about twice that. `fast` (delay 0.45 s) and `slow` (0.7 s) are two such clocks. `ring` and `side` (0.95 s each) are a ring of two, `ring` silenced by `side` and `side` driven by `ring`, so that `side` is on and off for about as long.
- **When:** `both` fires while `fast` and `slow` are on together. Their periods have no small common multiple, so this happens at irregular moments, every 2.3 s on average and never less than 1 s apart. `tick` fires for a moment as `both` comes on (`was`, a copy of `both` one delay late, stops it), while `enable` is on and `hold` is off.
- **Which side:** `go_left` fires with `tick` while `side` is on, `go_right` while it is off. `side` keeps its own rhythm, so the sides follow no short pattern, and come about as often.
- **How long:** `left` and `right` stretch the moment into a pulse of about 0.4 s, their delay.

Seen from outside, it behaves like a coin tossed now and then: about 130 pulses in 300 s, close to half to each side, with no repeating pattern of a few turns. But the same start always gives the same pulses: a vehicle that uses it behaves the same in every run, whatever the seed.

## Loading and validation

Loading fails, naming the file and the key, when:

- the module file is missing, or is not valid YAML;
- in the module file: `module`, `inputs`, `outputs` or `units` is missing, has the wrong type, or an unknown key appears; an input or unit name is not a valid name, or an input and a unit share a name; an output is not one of its units; a unit's input comes from something that is neither one of its units nor one of its inputs, or indexes an input; a unit has a `position`; or a unit is invalid as in a definition;
- in the definition: a module's `name` is not a valid name, or is already used; `file` or `inputs` is missing, or an unknown key appears; an input of the module is not given, or one is given that the module does not have; a source given to an input is not a sensor, unit or module output of the vehicle; a unit or actuator names a module's unit that is not an output, or a module that the vehicle does not include; or the module's `position` is outside the body.

## Acceptance criteria

1. **Loading:** a definition that includes `modules/wander.yaml` loads with its units renamed, such as `wander.left` and `wander.tick`, all threshold units; `wander.tick` has inputs from `wander.both` and `wander.was` and from the sources the definition gives `enable` (excitatory) and `hold` (inhibitory).
2. **Same as by hand:** the Vehicle 8 hunter, which includes the module, and the same hunter with the module's units written out by hand produce the same trajectory for the same seed.
3. **On and off:** a vehicle whose `enable` comes from a sensor wanders while the sensor reads 1: in 300 s, `left` and `right` together come on 100 to 160 times, each side 40% to 60% of them, never less than 1 s apart, each for about 0.4 s, and in no repeating pattern of up to 8 turns. While the sensor reads 0 they never fire. With a signal on `hold`, it does not fire. With `hold` given as `[]`, it fires as if `hold` were always off.
4. **Two copies:** a vehicle that includes the module twice, as `a` and `b`, has units `a.left`, `a.right`, `b.left` and `b.right`, wired to their own inputs.
5. **Private units:** naming a module's unit that is not an output, from outside the module, is an error.
6. **Validation:** each failure case under *Loading and validation* raises an error naming the file and the key.
7. **Diagram:** the diagram of a vehicle with the wander module has one part `wander`, of kind `module`, with 11 cells, at the module's position, and no part for its units. Its wires are only those that cross its edge, and a wire from `wander.left` starts at its cell.
8. **Headless:** loading a definition with modules never imports pygame.

## Out of scope

- **Parameters:** a module whose units take values from the including vehicle, such as other delays for each copy. A vehicle that needs other values uses another module file.
- **Modules inside modules**, sensors and motors in modules, and modules shared between vehicles at run time: each vehicle has its own copy.
- **Opening a module** in the diagram, to see its units and their wires.
